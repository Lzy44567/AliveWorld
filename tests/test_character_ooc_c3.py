import asyncio
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.capacity import capacity_report
from core.character_chat.cognition import public_index
from core.character_chat.context import build_context
from core.character_chat.context_contract import C3, M3, LEGACY
from core.character_chat.contract import plan_turn
from core.character_chat.models import CharacterSessionError, create_session, json_bytes, validate_session
from core.character_chat.ooc import normalize_ooc, OocInputError
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService, action_view, session_summary
from core.prompt_studio import SLICES, PromptOverrideStore, compose_prompt
from tests.test_character_chat_lifecycle import FakeTransport
from tests.test_character_memory import fixture, pending
from tests import test_character_chat_routes as route_fixtures


class OocInputTests(unittest.TestCase):
    def test_normalization_unicode_and_boundaries(self):
        for value in (None, '', ' \n\t '):
            self.assertEqual('', normalize_ooc(value))
        self.assertEqual('😀' * 1000, normalize_ooc(' \n' + '😀' * 1000 + '\t '))
        self.assertEqual('a\nb', normalize_ooc(' a\nb '))
        for value, code in ((False, 'INVALID_REQUEST'), (0, 'INVALID_REQUEST'), ([], 'INVALID_REQUEST'),
                            ({}, 'INVALID_REQUEST'), ('😀' * 1001, 'INPUT_LIMIT'), ('\ud800', 'INVALID_REQUEST')):
            with self.subTest(value=repr(value)):
                with self.assertRaises(OocInputError) as caught:
                    normalize_ooc(value)
                self.assertEqual(code, caught.exception.code)

    def test_c3_recall_closure_and_no_ooc_in_evidence(self):
        value = fixture(25)
        p = dict(pending('coffee'), ooc_note='SECRET_CONTROL')
        plan, allowed, ids, report = build_context(value, p, context_contract_id=C3)
        data = json.loads(plan.user_prompt)
        self.assertEqual(C3, data['context_contract_id'])
        self.assertEqual('SECRET_CONTROL', data['current_ooc_note'])
        self.assertEqual('coffee', data['current_user_message']['content'])
        self.assertEqual(1, len(data['recalled_sources']))
        self.assertEqual({m['message_id'] for m in data['history'] + data['recalled_sources']}, {m['message_id'] for m in allowed})
        self.assertEqual({e['entry_id'] for e in data['ledger']}, ids)
        self.assertIn('source_recall', report)
        self.assertNotIn('SECRET_CONTROL', json.dumps(allowed))
        self.assertTrue(all(item['contextContractId'] == C3 for item in plan.prompt_manifest))

    def test_ooc_alone_does_not_trigger_world_or_memory_recall(self):
        value = fixture(25)
        value['world_binding'] = {'snapshot': {'name': '合成', 'entries': [
            {'id': 'control', 'name': 'SECRET_TRIGGER', 'keywords': ['SECRET_TRIGGER'], 'content': '世界条目', 'tags': [], 'is_active': True}]}}
        p = dict(pending('ordinary'), ooc_note='coffee SECRET_TRIGGER')
        plan, _, _, report = build_context(value, p, context_contract_id=C3)
        data = json.loads(plan.user_prompt)
        self.assertEqual([], data['recalled_sources'])
        self.assertEqual([], data['world_related_entries'])
        self.assertEqual([], report['source_recall']['entries'])
        _, _, _, plain_report = build_context(value, pending('ordinary'))
        self.assertEqual(plain_report['memory_context'], report['memory_context'])

    def test_ooc_is_required_budget_input_never_trimmed(self):
        value = fixture(25)
        observations = []
        def budget(system, raw, **kwargs):
            data = json.loads(raw)
            observations.append(data)
            self.assertIn('current_ooc_note', system)
            return {'fits': not data['ledger'] and len(data['history']) == 4}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            plan, _, _, report = build_context(value, dict(pending('coffee'), ooc_note='😀' * 1000), context_contract_id=C3)
        self.assertGreater(len(observations), 1)
        self.assertTrue(all(d['current_ooc_note'] == '😀' * 1000 for d in observations))
        self.assertFalse(any(o.get('field') == 'current_ooc_note' for o in report['omitted']))
        self.assertEqual('😀' * 1000, json.loads(plan.user_prompt)['current_ooc_note'])

    def test_invalid_context_input_identity_fail_closed(self):
        for context, note in ((M3, 'control'), (LEGACY, 'control'), (C3, None)):
            p = pending('台词')
            if note is not None:
                p['ooc_note'] = note
            with self.assertRaises(CharacterSessionError):
                build_context(fixture(0), p, context_contract_id=context)

    def test_ooc_only_quote_and_forged_id_are_not_sources(self):
        value = fixture(0)
        p = dict(pending('正式台词'), ooc_note='秘密提示')
        _, allowed, ids, _ = build_context(value, p, context_contract_id=C3)
        action = {'action_id': str(uuid4())}
        attempt = {'request_id': str(uuid4()), 'pending_input': p, 'base_revision': 0}
        for mid in (p['user_message_id'], str(uuid4())):
            op = {'op': 'add', 'kind': 'knowledge', 'content': '秘密提示', 'source': {'type': 'player_statement',
                'message_ids': [mid], 'evidence': [{'message_id': mid, 'quote': '秘密提示'}]},
                'visibility': {'audience_instance_ids': [part['instance_id'] for part in value['participants']]}}
            with self.assertRaises(CharacterSessionError) as caught:
                plan_turn(value, action, attempt, json.dumps({'reply': '回应', 'ledger_ops': [op]}), allowed, ids)
            self.assertEqual('CONTRACT_INVALID', caught.exception.code)

    def test_prompt_protocols_overrides_and_required_ooc_identity(self):
        by_id = {s.id: s for s in SLICES}
        with tempfile.TemporaryDirectory() as directory:
            store = PromptOverrideStore(Path(directory) / 'overrides.json')
            for old in ('character.reply.core', 'character.reply.v2.core', 'character.reply.m3.v1.core', 'character.reply.m3.v2.core'):
                store.save(old, 'OLD_ONLY_OVERRIDE')
            for version in (1, 2):
                task = f'character.reply.c3.v{version}'
                self.assertFalse(by_id[task + '.ooc'].editable)
                self.assertTrue(by_id[task + '.ooc'].required)
                system = compose_prompt(task, {'character.presentation_mode': 'roleplay'}, store=store)
                self.assertNotIn('OLD_ONLY_OVERRIDE', system.text)
                self.assertIn('需要玩家选择处停止', system.text)
                self.assertIn('不能把拒绝改判为同意', system.text)
                self.assertIn('current_ooc_note', system.text)
                self.assertNotIn('本请求使用character.context.m3.v1', system.text)
                store.save(task + '.core', 'C3_CUSTOM_CORE')
                system = compose_prompt(task, {'character.presentation_mode': 'roleplay'}, store=store)
                self.assertIn('C3_CUSTOM_CORE', system.text)
                self.assertIn('current_ooc_note', system.text)
                self.assertIn('严格 JSON', system.text)


class OocLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))
        self.transport = FakeTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        self.sid = self.repo.create(create_session(str(uuid4()), {'name': '合成', 'description': '冻结人设'},
            {'kind': 'character', 'key': '合成'}))['session_id']

    def payload(self, **extra):
        return {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'],
                'operation': 'send', 'delivery': 'non_stream', 'content': '正式台词', **extra}

    async def execute(self, payload):
        start = self.service.begin(self.sid, payload)
        return await self.service.execute(start['job']['request_id'], lambda *_: None) if 'job' in start else start['existing']

    def assert_code(self, code, fn):
        with self.assertRaises(CharacterSessionError) as caught:
            fn()
        self.assertEqual(code, caught.exception.code)

    async def test_success_persistence_visibility_no_extra_message_and_next_turn_exclusion(self):
        for delivery in ('stream', 'non_stream'):
            result = await self.execute(self.payload(ooc_note='  合成秘密提示  ', delivery=delivery))
            self.assertEqual('合成秘密提示', result['turn']['ooc_note'])
            self.assertEqual('正式台词', result['turn']['user_message']['content'])
            self.assertEqual(C3, self.transport.plans[-1].context_contract_id)
            self.assertEqual('character.reply.v2', self.transport.plans[-1].contract_id)
        value = self.repo.load(self.sid)
        self.assertEqual(2, len(value['turns']))
        self.assertEqual([], value['ledger'])
        self.assertNotIn('合成秘密提示', json.dumps(session_summary(value), ensure_ascii=False))
        before_capacity = capacity_report(value)
        before_index = public_index(value)
        for turn in value['turns']:
            turn.pop('ooc_note')
        self.assertEqual(before_capacity, capacity_report(value))
        self.assertEqual(before_index, public_index(value))
        await self.execute(self.payload(content='下一轮'))
        data = json.loads(self.transport.plans[-1].user_prompt)
        self.assertNotIn('current_ooc_note', data)
        self.assertNotIn('合成秘密提示', json.dumps(data, ensure_ascii=False))
        self.assertEqual(M3, self.transport.plans[-1].context_contract_id)

    async def test_no_ooc_fingerprint_unchanged_null_and_blank_duplicate(self):
        payload = self.payload(content='（动作）[[伪场外]]')
        result = await self.execute(payload)
        action = self.repo.load(self.sid)['requests'][0]
        identity = {'operation': 'send', 'content': payload['content'], 'target_turn_id': None, 'mode': 'messenger'}
        self.assertEqual(hashlib.sha256(json_bytes(identity)).hexdigest(), action['fingerprint'])
        for note in (None, '', ' \n '):
            duplicate = await self.execute({**payload, 'ooc_note': note})
            self.assertEqual(result['request_id'], duplicate['request_id'])
            self.assertNotIn('ooc_note', duplicate['turn'])
        self.assertEqual(1, self.transport.calls)
        self.assertEqual(payload['content'], result['turn']['user_message']['content'])

    async def test_ooc_fingerprint_duplicate_and_mismatch(self):
        payload = self.payload(ooc_note=' control ')
        start = self.service.begin(self.sid, payload)
        same = self.service.begin(self.sid, {**payload, 'ooc_note': 'control'})
        self.assertEqual(start['job']['request_id'], same['existing']['request_id'])
        self.assert_code('IDEMPOTENCY_MISMATCH', lambda: self.service.begin(self.sid, {**payload, 'ooc_note': 'other'}))
        result = await self.service.execute(start['job']['request_id'], lambda *_: None)
        duplicate = await self.execute(payload)
        self.assertEqual(result['request_id'], duplicate['request_id'])
        self.assertEqual(1, self.transport.calls)

    async def test_invalid_input_and_ooc_only_zero_calls(self):
        for extra in ({'content': '', 'ooc_note': 'only'}, {'ooc_note': False}, {'ooc_note': 0},
                      {'ooc_note': ['x']}, {'ooc_note': '\ud800'}, {'ooc_note': '😀' * 1001}):
            code = 'INPUT_LIMIT' if extra.get('ooc_note') == '😀' * 1001 else 'INVALID_REQUEST'
            self.assert_code(code, lambda: self.service.begin(self.sid, self.payload(**extra)))
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], self.repo.load(self.sid)['requests'])

    async def test_failed_retry_original_pair_and_current_preference_authorization(self):
        self.service.metadata(self.sid, 0, preference_settings={'enabled': True, 'include_sensitive': True})
        self.service.preference_loader = lambda _: [{'content': 'AUTHORIZED_SYNTHETIC'}]
        self.transport.raw = 'bad-json'
        payload = self.payload(ooc_note='control')
        failed = await self.execute(payload)
        self.assertEqual('control', failed['retry_ooc_note'])
        self.assertEqual('正式台词', failed['retry_input'])
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        self.service.metadata(self.sid, self.repo.load(self.sid)['revision'], preference_settings={'enabled': False, 'include_sensitive': False})
        self.transport.raw = None
        retry = {'expected_revision': self.repo.load(self.sid)['revision'], 'retry_of': failed['request_id'], 'retry_token': str(uuid4()), 'delivery': 'stream'}
        for key in ('content', 'ooc_note'):
            self.assert_code('INVALID_REQUEST', lambda: self.service.begin(self.sid, {**retry, key: 'replacement'}, retry_action_id=payload['client_action_id']))
        job = self.service.begin(self.sid, retry, retry_action_id=payload['client_action_id'])['job']
        result = await self.service.execute(job['request_id'], lambda *_: None)
        data = json.loads(self.transport.plans[-1].user_prompt)
        self.assertEqual('control', data['current_ooc_note'])
        self.assertNotIn('user_preferences', data)
        self.assertEqual('control', result['turn']['ooc_note'])
        duplicate = self.service.begin(self.sid, retry, retry_action_id=payload['client_action_id'])
        self.assertEqual(result['request_id'], duplicate['existing']['request_id'])
        self.assertEqual(2, self.transport.calls)

    async def test_cancel_before_execute_zero_calls_and_retry_pair(self):
        payload = self.payload(ooc_note='control')
        job = self.service.begin(self.sid, payload)['job']
        cancelled = self.service.cancel(self.sid, job['request_id'])
        self.assertEqual('control', cancelled['retry_ooc_note'])
        await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        self.assertNotIn('pending_input', self.repo.load(self.sid)['requests'][0]['attempts'][0])

    async def test_cancel_inflight_and_commit_wins(self):
        self.transport.gate, self.transport.started = asyncio.Event(), asyncio.Event()
        job = self.service.begin(self.sid, self.payload(ooc_note='control'))['job']
        task = asyncio.create_task(self.service.execute(job['request_id'], lambda *_: None))
        await self.transport.started.wait()
        self.service.cancel(self.sid, job['request_id'])
        result = await task
        self.assertEqual('cancelled', result['status'])
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        self.transport.gate = self.transport.started = None
        committed = await self.execute(self.payload(ooc_note='control'))
        after = self.service.cancel(self.sid, committed['request_id'])
        self.assertEqual('already_committed', after['cancel_result'])
        self.assertEqual('control', after['turn']['ooc_note'])

    async def test_restart_pending_interrupted_retry_and_no_get_rewrite(self):
        payload = self.payload(ooc_note='control')
        job = self.service.begin(self.sid, payload)['job']
        path = self.repo.directory / (self.sid + '.json')
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.repo.load(self.sid)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
        recovered = CharacterChatService(self.repo, self.transport)
        value = self.repo.load(self.sid)
        action = value['requests'][0]
        self.assertEqual('interrupted', action['attempts'][0]['status'])
        self.assertEqual('control', action_view(value, action)['retry_ooc_note'])
        retry = {'expected_revision': 0, 'retry_of': job['request_id'], 'retry_token': str(uuid4())}
        new = recovered.begin(self.sid, retry, retry_action_id=payload['client_action_id'])['job']
        result = await recovered.execute(new['request_id'], lambda *_: None)
        self.assertEqual('control', result['turn']['ooc_note'])
        self.assertEqual(1, self.transport.calls)

    async def test_regenerate_failure_success_archive_undo_exclusion(self):
        first = await self.execute(self.payload(ooc_note='control'))
        def regen():
            p = self.payload(operation='regenerate', target_turn_id=first['turn_id'])
            p.pop('content')
            return p
        payload = regen()
        for key in ('ooc_note', 'content'):
            for replacement in (None, '', 'replacement'):
                self.assert_code('INVALID_REQUEST', lambda: self.service.begin(self.sid, {**payload, key: replacement}))
        self.transport.raw = 'bad-json'
        failed = await self.execute(payload)
        self.assertEqual('control', failed['retry_ooc_note'])
        self.assertEqual(first['turn_id'], self.repo.load(self.sid)['turns'][0]['turn_id'])
        self.transport.raw = None
        replaced = await self.execute(regen())
        value = self.repo.load(self.sid)
        self.assertEqual('control', value['turns'][0]['ooc_note'])
        self.assertEqual('control', value['requests'][0]['archived_turn']['ooc_note'])
        payload = self.payload(operation='undo', target_turn_id=replaced['turn_id'])
        payload.pop('content')
        self.assert_code('INVALID_REQUEST', lambda: self.service.begin(self.sid, {**payload, 'ooc_note': ''}))
        self.service.begin(self.sid, payload)
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        await self.execute(self.payload(content='下一轮'))
        data = json.loads(self.transport.plans[-1].user_prompt)
        self.assertNotIn('current_ooc_note', data)
        self.assertEqual([], data['history'])

    async def test_atomic_write_failure_no_half_turn_then_restart(self):
        job = self.service.begin(self.sid, self.payload(ooc_note='control'))['job']
        before = self.repo.load(self.sid)
        with patch.object(self.repo, '_write', side_effect=CharacterSessionError('PERSISTENCE_FAILED')):
            result = await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual('PERSISTENCE_FAILED', result['error_code'])
        self.assertEqual(before, self.repo.load(self.sid))
        CharacterChatService(self.repo, self.transport)
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        self.assertEqual('control', self.repo.load(self.sid)['requests'][0]['retry_input']['ooc_note'])

    async def test_context_limit_zero_provider_preserves_retry_ooc(self):
        with patch('core.character_chat.context.budget_report', return_value={'fits': False}):
            self.assert_code('CONTEXT_LIMIT', lambda: self.service.begin(self.sid, self.payload(ooc_note='😀' * 1000)))
        value = self.repo.load(self.sid)
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], value['turns'])
        self.assertEqual('😀' * 1000, action_view(value, value['requests'][0])['retry_ooc_note'])

    async def test_storage_optional_fields_and_context_identity_fail_closed(self):
        job = self.service.begin(self.sid, self.payload(ooc_note='control'))['job']
        pending_value = self.repo.load(self.sid)
        for input_key in ('pending_input', 'retry_input'):
            for bad in (None, '', ' padded ', False, '😀' * 1001, '\ud800'):
                value = copy.deepcopy(pending_value)
                target = value['requests'][0]['attempts'][0][input_key] if input_key == 'pending_input' else value['requests'][0][input_key]
                target['ooc_note'] = bad
                self.assert_code('SESSION_CORRUPT', lambda: validate_session(value))
        for mutation in ('missing_pending', 'missing_retry', 'wrong_context', 'wrong_retry_context'):
            value = copy.deepcopy(pending_value)
            action = value['requests'][0]
            if mutation == 'missing_pending': action['attempts'][0]['pending_input'].pop('ooc_note')
            elif mutation == 'missing_retry': action['retry_input'].pop('ooc_note')
            elif mutation == 'wrong_context': action['attempts'][0]['context_contract_id'] = M3
            else: action['retry_input']['context_contract_id'] = M3
            self.assert_code('SESSION_CORRUPT', lambda: validate_session(value))
        result = await self.service.execute(job['request_id'], lambda *_: None)
        active = self.repo.load(self.sid)
        for bad in (False, '', ' padded ', '😀' * 1001):
            value = copy.deepcopy(active)
            value['turns'][0]['ooc_note'] = bad
            self.assert_code('SESSION_CORRUPT', lambda: validate_session(value))
        value = copy.deepcopy(active)
        value['requests'][0]['attempts'][0]['context_contract_id'] = LEGACY
        self.assert_code('SESSION_CORRUPT', lambda: validate_session(value))
        self.service.begin(self.sid, {k: v for k, v in self.payload(operation='undo', target_turn_id=result['turn_id']).items() if k != 'content'})
        archived = self.repo.load(self.sid)
        archived['requests'][0]['archived_turn']['ooc_note'] = ' padded '
        self.assert_code('SESSION_CORRUPT', lambda: validate_session(archived))

    async def test_unknown_context_cannot_load_write_or_recover(self):
        job = self.service.begin(self.sid, self.payload(ooc_note='control'))['job']
        value = self.repo.load(self.sid)
        value['requests'][0]['attempts'][0]['context_contract_id'] = 'character.context.future'
        with patch('core.character_chat.repository.validate_session'):
            self.repo._write(value)
        path = self.repo.directory / (self.sid + '.json')
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with patch.object(self.repo, '_write') as write:
            self.assert_code('CONTEXT_CONTRACT_UNSUPPORTED', lambda: self.repo.load(self.sid))
            CharacterChatService(self.repo, self.transport)
            write.assert_not_called()
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
        self.assertEqual(0, self.transport.calls)

    async def test_reply_v1_independent_of_c3_context(self):
        self.repo.transaction(self.sid, lambda value: (value['extensions'].pop('character_memory'), True))
        result = await self.execute(self.payload(ooc_note='control'))
        self.assertEqual('committed', result['status'])
        self.assertEqual('character.reply.v1', self.transport.plans[-1].contract_id)
        self.assertEqual(C3, self.transport.plans[-1].context_contract_id)


class OocRouteTests(unittest.TestCase):
    setUp = route_fixtures.CharacterRouteTests.setUp

    def test_whitelist_public_history_source_exclusion_and_retry_replacements(self):
        url = self.prefix + '/' + self.sid
        self.transport.with_ledger = True
        payload = {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send',
                   'delivery': 'non_stream', 'content': '正式台词', 'ooc_note': 'control'}
        result = self.client.post(url + '/actions', json=payload)
        self.assertEqual(200, result.status_code)
        turn = result.json()['turn']
        self.assertEqual('control', turn['ooc_note'])
        self.assertEqual('control', self.client.get(url).json()['turns'][0]['ooc_note'])
        self.assertEqual('control', self.client.get(url + '/turns').json()['turns'][0]['ooc_note'])
        entry = result.json()['ledger'][0]['entry_id']
        source = self.client.get(url + '/memory/' + entry + '/sources').json()
        self.assertNotIn('control', json.dumps(source))
        self.assertNotIn('control', self.client.get(self.prefix + '?view=summary').text)
        for operation in ('regenerate', 'undo'):
            for key in ('content', 'ooc_note'):
                for replacement in (None, '', 'replacement'):
                    response = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()),
                        'expected_revision': 1, 'operation': operation, 'target_turn_id': turn['turn_id'], key: replacement})
                    self.assertEqual(400, response.status_code)
        for key in ('content', 'ooc_note'):
            response = self.client.post(url + '/actions/' + payload['client_action_id'] + '/retry', json={
                'expected_revision': 1, 'retry_of': result.json()['request_id'], 'retry_token': str(uuid4()), key: 'replacement'})
            self.assertEqual(400, response.status_code)
        self.assertEqual(1, self.transport.calls)

    def test_invalid_ooc_inputs_zero_calls_safe_errors(self):
        url = self.prefix + '/' + self.sid
        for note in (False, 0, [], {}, '😀' * 1001, '\ud800'):
            payload = {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send',
                       'delivery': 'non_stream', 'content': '正式台词', 'ooc_note': note}
            response = self.client.post(url + '/actions', content=json.dumps(payload, ensure_ascii=True),
                                        headers={'Content-Type': 'application/json'})
            self.assertEqual(413 if isinstance(note, str) and len(note) > 1000 else 400, response.status_code)
            self.assertNotIn('ooc_note', response.text)
        self.assertEqual(0, self.transport.calls)
