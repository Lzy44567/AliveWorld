import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.annotations import validate_annotation, automatic_grades, chain_root
from core.character_chat.contract import parse_result
from core.character_chat.context import build_context
from core.character_chat.memory import settings, select_memory, public_state, valid_candidates
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.protocol import V1, V2
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService, action_by_id, action_view, visible_turn
from core.character_chat.stream_json import ReplyPreview
from core.prompt_studio import compose_prompt, PromptOverrideStore
from tests.test_character_chat_lifecycle import FakeTransport
from tests.test_character_memory import fixture, pending
from tests import test_character_chat_routes as route_fixtures


class AnnotationTransport(FakeTransport):
    reason = 'explicit_boundary'
    private = False
    duplicate = False
    def response(self, plan):
        data = json.loads(plan.user_prompt)
        ids = {p['controller']: p['instance_id'] for p in data['participants']}
        current = data['current_user_message']
        source = {'type': 'player_statement', 'message_ids': [current['message_id']],
                  'evidence': [{'message_id': current['message_id'], 'quote': current['content'][:240]}]}
        kind = 'knowledge'
        if self.reason in {'relationship_turn', 'conflict_repair'}:
            source['type'], kind = 'model_inference', 'relationship'
        elif self.reason == 'goal_turn':
            source['type'], kind = 'model_inference', 'intent'
        if self.duplicate:
            source = copy.deepcopy(data['ledger'][0]['source'])
        op = {'op': 'add', 'kind': kind, 'content': current['content'][:400], 'about_instance_id': ids['user'],
              'source': source, 'visibility': {'audience_instance_ids': [ids['ai']] if self.private else list(ids.values())}}
        if self.supersede:
            op.update(op='supersede', target_entry_id=data['ledger'][0]['entry_id'])
        result = {'reply': '自然回应', 'ledger_ops': [op]}
        if plan.contract_id == V2:
            result['memory_annotations'] = [{'op_index': 0, 'reason': self.reason}] if self.reason else []
        return result

    async def generate(self, config, plan, report, delivery, emit):
        self.calls += 1
        self.plans.append(plan)
        if self.gate:
            await self.gate.wait()
        return self.raw if self.raw is not None else json.dumps(self.response(plan), ensure_ascii=False)


class M2ProtocolTests(unittest.TestCase):
    def test_v1_v2_exact_keys_indices_types_duplicates_and_limits(self):
        v1 = {'reply': '回应', 'ledger_ops': []}
        v2 = dict(v1, memory_annotations=[])
        self.assertEqual(v1, parse_result(json.dumps(v1), V1))
        self.assertEqual(v2, parse_result(json.dumps(v2), V2))
        bad = [(v1, V2), (v2, V1), (dict(v2, extra=0), V2), (v2, 'character.reply.v99')]
        for annotations in ([{'op_index': True, 'reason': 'explicit_boundary'}], [{'op_index': -1, 'reason': 'commitment'}],
                            [{'op_index': 0, 'reason': 'unknown'}], [{'op_index': 0, 'reason': 'commitment', 'level': 'important'}], [{}] * 7):
            bad.append((dict(v2, memory_annotations=annotations), V2))
        for value, contract in bad:
            with self.subTest(value=value, contract=contract), self.assertRaises(CharacterSessionError):
                parse_result(json.dumps(value), contract)
        duplicate = {'reply': '回应', 'ledger_ops': [{}], 'memory_annotations': [{'op_index': 0, 'reason': 'commitment'}] * 2}
        with self.assertRaises(CharacterSessionError):
            parse_result(json.dumps(duplicate), V2)
        with self.assertRaises(CharacterSessionError):
            parse_result('{"reply":"x","ledger_ops":[],"memory_annotations":[],"memory_annotations":[]}', V2)

    def test_preview_every_split_v2_never_exposes_annotation_nested_reply(self):
        raw = '{"reply":"中文🙂","ledger_ops":[],"memory_annotations":[{"reason":"explicit_boundary","reply":"PRIVATE"}]}'
        for split in range(len(raw) + 1):
            pieces = []
            lexer = ReplyPreview(pieces.append, V2)
            lexer.feed(raw[:split]); lexer.feed(raw[split:])
            self.assertEqual('中文🙂', ''.join(pieces))
        with self.assertRaises(CharacterSessionError):
            ReplyPreview(lambda _: None, V1).feed(raw)

    def test_reason_evidence_matrix_and_annotation_version(self):
        user = str(uuid4())
        entry = {'kind': 'knowledge', 'source': {'type': 'player_statement'}, 'about_instance_id': user}
        for reason in ('explicit_boundary', 'explicit_preference', 'commitment'):
            self.assertEqual(reason, validate_annotation({'version': 1, 'reason': reason}, entry, user)['reason'])
        for changes in ({'version': 2}, {'version': True}, {'extra': 'meaning'}, {'reason': 'emotion_score'}):
            with self.assertRaises(ValueError):
                validate_annotation({'version': 1, 'reason': 'explicit_boundary', **changes}, entry, user)
        for reason, source, kind, about, valid in (
            ('explicit_boundary', 'model_inference', 'belief', user, False),
            ('explicit_preference', 'player_statement', 'knowledge', None, False),
            ('commitment', 'model_inference', 'intent', user, False),
            ('relationship_turn', 'model_inference', 'relationship', user, True),
            ('conflict_repair', 'model_inference', 'belief', user, False),
            ('relationship_turn', 'dialogue_event', 'experience', None, True),
            ('goal_turn', 'model_inference', 'intent', None, True),
            ('goal_turn', 'player_statement', 'knowledge', user, False)):
            value = {'kind': kind, 'source': {'type': source}, 'about_instance_id': about}
            if valid:
                validate_annotation({'version': 1, 'reason': reason}, value, user)
            else:
                with self.assertRaises(ValueError): validate_annotation({'version': 1, 'reason': reason}, value, user)

    def test_automatic16_manual8_32_budget_and_public_report(self):
        value = fixture(50)
        user = value['participants'][0]['instance_id']
        value['extensions']['character_memory'] = {'version': 2, 'important_entry_ids': [value['ledger'][-1]['entry_id']],
            'dismissed_auto_root_ids': [], 'notice_ack_revision': 0}
        for e in value['ledger'][:40]:
            e.update(about_instance_id=user, memory_annotation={'version': 1, 'reason': 'explicit_boundary'})
        selected, report = select_memory(value, '普通')
        self.assertEqual(32, len(selected)); self.assertEqual(value['ledger'][-1]['entry_id'], selected[0]['entry_id'])
        self.assertEqual(16, sum(e['reason'].startswith('auto_') for e in report))
        value['ledger'][0]['visibility']['audience_instance_ids'] = [value['ledger'][0]['subject_instance_id']]
        with patch('core.character_chat.context.budget_report', side_effect=lambda _, raw, **kw: {'fits': not json.loads(raw)['ledger']}):
            plan, messages, ids, budget = build_context(value, pending('海边'))
        self.assertEqual(set(), ids)
        self.assertEqual([], json.loads(plan.user_prompt)['ledger'])
        self.assertNotIn(value['ledger'][0]['entry_id'], json.dumps(budget['memory_context']))
        self.assertTrue(any(e['state'] == 'budget' for e in budget['memory_context']['entries']))
        self.assertNotIn(value['turns'][0]['user_message'], messages)

    def test_v2_manifest_and_core_override_do_not_inherit_v1(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptOverrideStore(Path(directory) / 'overrides.json')
            store.save('character.reply.core', 'OLD_V1_OVERRIDE')
            v1 = compose_prompt('character.reply', {'character.presentation_mode': 'messenger'}, store=store)
            v2 = compose_prompt('character.reply.v2', {'character.presentation_mode': 'messenger'}, store=store)
            self.assertIn('OLD_V1_OVERRIDE', v1.text); self.assertNotIn('OLD_V1_OVERRIDE', v2.text)
            self.assertIn('memory_annotations', v2.text)
            self.assertEqual(['character.reply.v2.core', 'character.reply.v2.contract', 'character.reply.v2.presentation'], [m['sliceId'] for m in v2.manifest])


class M2LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))
        self.transport = AnnotationTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        self.sid = self.repo.create(create_session(str(uuid4()), {'name': '合成角色', 'description': '固定资料'}, {'kind': 'character', 'key': '合成'}))['session_id']

    def value(self): return self.repo.load(self.sid)
    def update(self, operation, *args, revision=None):
        return self.service.memory_update(self.sid, self.value()['revision'] if revision is None else revision, operation, *args)
    def begin(self, operation='send', content='安静表达：请尊重我的边界'):
        value = self.value()
        payload = {'client_action_id': str(uuid4()), 'expected_revision': value['revision'], 'operation': operation, 'delivery': 'non_stream'}
        payload.update(content=content) if operation == 'send' else payload.update(target_turn_id=value['turns'][-1]['turn_id'])
        return self.service.begin(self.sid, payload)
    async def send(self, operation='send', content='安静表达：请尊重我的边界'):
        begun = self.begin(operation, content)
        return await self.service.execute(begun['job']['request_id'], lambda *_: None) if 'job' in begun else begun['existing']

    async def test_new_v2_public_notice_ack_source_and_strict_projection(self):
        self.assertEqual(2, settings(self.value())['version'])
        events = []
        begun = self.begin()
        result = await self.service.execute(begun['job']['request_id'], lambda name, data: events.append((name, data)))
        notice = result['memory_notice']
        self.assertEqual({'action_id', 'committed_revision', 'entry_ids'}, set(notice))
        self.assertNotIn('memory_notice', events[0][1])
        self.assertEqual([], result['memory_context_report']['entries'])  # New output is not input memory.
        entry = self.value()['ledger'][0]
        self.assertEqual('安静表达：请尊重我的边界', self.service.memory_sources(self.sid, entry['entry_id'])['messages'][0]['content'])
        view = action_view(self.value(), action_by_id(self.value(), result['action_id']))
        self.assertEqual(notice, view['memory_notice'])
        self.assertNotIn('memory_notice', visible_turn(self.value()['turns'][0]))
        ack = self.update('acknowledge', result['action_id'])
        self.assertEqual({'session_id', 'revision', 'memory_settings'}, set(ack))
        self.assertEqual(1, ack['memory_settings']['notice_ack_revision'])
        revision = ack['revision']; self.assertEqual(revision, self.update('acknowledge', result['action_id'])['revision'])
        with self.assertRaises(CharacterSessionError): self.update('acknowledge', str(uuid4()))

    async def test_cancel_restore_manual_independent_supersede_undo_and_no_notice(self):
        first = await self.send(); root = self.value()['ledger'][0]['entry_id']
        self.update('selection', root, True)
        self.service.memory_mark(self.sid, self.value()['revision'], root, True)
        self.assertEqual(2, settings(self.value())['version'])
        self.transport.supersede = True
        revised = await self.send(content='更正：仍然不要这样做')
        self.assertNotIn('memory_notice', revised)
        value = self.value(); new = next(e for e in value['ledger'] if e['status'] == 'active')
        self.assertEqual(root, chain_root(new, value))
        state = public_state(value)
        self.assertTrue(state['automatic_entries'][0]['dismissed'])
        self.assertEqual(root, state['protected_entries'][0]['root_entry_id'])
        self.assertEqual('important', select_memory(value, '继续')[1][0]['reason'])
        await self.send(operation='undo')
        self.assertTrue(public_state(self.value())['automatic_entries'][0]['dismissed'])
        self.update('selection', root, False)
        self.assertFalse(public_state(self.value())['automatic_entries'][0]['dismissed'])
        regenerated = await self.send(operation='regenerate')
        self.assertNotIn('memory_notice', regenerated)

    async def test_cancel_source_then_release_no_resurrection_or_ack_watermark_rollback(self):
        result = await self.send(); eid = self.value()['ledger'][0]['entry_id']
        self.update('selection', eid, True); self.update('acknowledge', result['action_id'])
        await self.send(operation='undo')
        state = public_state(self.value())
        self.assertEqual([], state['automatic_entries']); self.assertEqual([eid], state['inactive_dismissed_root_ids'])
        self.assertEqual(1, state['notice_ack_revision'])
        self.assertEqual(self.value()['revision'], self.update('acknowledge', result['action_id'])['revision'])
        self.update('release', eid); self.assertEqual([], settings(self.value())['dismissed_auto_root_ids'])

    async def test_private_no_public_event_no_release_for_private_successor(self):
        first = await self.send(); root = self.value()['ledger'][0]['entry_id']
        self.update('selection', root, True)
        self.transport.supersede = True; self.transport.private = True
        result = await self.send(content='角色私有解释')
        self.assertNotIn('memory_notice', result)
        state = public_state(self.value())
        self.assertEqual([], state['automatic_entries']); self.assertEqual([], state['inactive_dismissed_root_ids'])
        with self.assertRaises(CharacterSessionError): self.update('release', root)
        with self.assertRaises(CharacterSessionError): self.update('acknowledge', result['action_id'])
        self.assertNotIn('角色私有解释', json.dumps(state))
        self.assertNotIn('memory_notice', action_view(self.value(), action_by_id(self.value(), first['action_id'])))
        self.assertEqual(self.value()['revision'], self.update('acknowledge', first['action_id'])['revision'])

    async def test_same_exact_evidence_duplicate_has_no_priority_or_notice(self):
        await self.send(); first = self.value()['ledger'][0]['entry_id']
        self.transport.duplicate = True
        result = await self.send(content='模型重复转述')
        self.assertEqual('committed', result['status']); self.assertNotIn('memory_notice', result)
        grades = automatic_grades(self.value(), valid_candidates(self.value()), [])
        self.assertEqual({first: 'important'}, grades)
        self.update('selection', first, True)
        self.assertEqual({}, automatic_grades(self.value(), valid_candidates(self.value()), [first]))

    async def test_old_v1_read_no_migration_frozen_recovery_and_retry_upgrade(self):
        value = self.value(); value['extensions'].pop('character_memory')
        value['revision'] += 1; self.repo.save(value, expected_revision=0)
        path = self.repo.directory / (self.sid + '.json'); before = path.read_bytes()
        public_state(self.value()); self.assertEqual(before, path.read_bytes())
        begun = self.begin(); rid = begun['job']['request_id']
        value = self.value(); action = value['requests'][0]
        self.assertEqual(V1, action['attempts'][0]['reply_contract_id']); self.assertEqual(V1, action['retry_input']['reply_contract_id'])
        self.assertEqual(V1, self.service.jobs[rid]['plan'].contract_id)
        with self.assertRaises(CharacterSessionError): self.update('enable', True)
        self.service.cancel(self.sid, rid); await self.service.execute(rid, lambda *_: None)
        self.update('enable', True)
        retry = self.service.begin(self.sid, {'expected_revision': self.value()['revision'], 'retry_of': rid, 'retry_token': str(uuid4())}, retry_action_id=action['action_id'])
        await self.service.execute(retry['job']['request_id'], lambda *_: None)
        attempts = self.value()['requests'][0]['attempts']
        self.assertEqual([V1, V2], [a['reply_contract_id'] for a in attempts])
        second = self.begin(); second_rid = second['job']['request_id']
        recovered = CharacterChatService(self.repo, self.transport)
        value = self.value(); retry_input = value['requests'][-1]['retry_input']
        self.assertEqual(V2, retry_input['reply_contract_id']); self.assertEqual('interrupted', value['requests'][-1]['attempts'][0]['status'])
        self.service.cancel(self.sid, second_rid); await self.service.execute(second_rid, lambda *_: None)

    async def test_cas_busy_save_failure_invalid_annotation_and_regenerate_failure(self):
        first = await self.send(); eid = self.value()['ledger'][0]['entry_id']
        with self.assertRaises(CharacterSessionError): self.update('selection', eid, True, revision=0)
        before = self.value()
        with patch('core.character_chat.repository.os.replace', side_effect=OSError('synthetic')):
            with self.assertRaises(CharacterSessionError): self.update('selection', eid, True)
        self.assertEqual(before, self.value())
        begun = self.begin()
        with self.assertRaises(CharacterSessionError): self.update('acknowledge', first['action_id'])
        raw = self.transport.response(self.service.jobs[begun['job']['request_id']]['plan'])
        raw['memory_annotations'][0]['op_index'] = True; self.transport.raw = json.dumps(raw)
        result = await self.service.execute(begun['job']['request_id'], lambda *_: None)
        self.assertEqual('CONTRACT_INVALID', result['error_code'])
        self.assertEqual(before['ledger'], self.value()['ledger']); self.assertEqual(before['turns'], self.value()['turns'])
        result = await self.send(operation='regenerate')
        self.assertEqual('failed', result['status']); self.assertEqual(before['turns'], self.value()['turns'])

    async def test_persisted_annotation_and_notification_tamper_fail_closed(self):
        await self.send(); baseline = self.value()
        for mutation in ('annotation_version', 'wrong_reason_source', 'notice_entry', 'protocol', 'inverse', 'v1_annotation', 'ai_statement'):
            value = copy.deepcopy(baseline); value['revision'] += 1
            if mutation == 'annotation_version': value['ledger'][0]['memory_annotation']['version'] = 2
            if mutation == 'wrong_reason_source': value['ledger'][0]['memory_annotation']['reason'] = 'relationship_turn'
            if mutation == 'notice_entry': value['turns'][0]['memory_notice']['entry_ids'] = [str(uuid4())]
            if mutation == 'protocol': value['requests'][0]['attempts'][0]['reply_contract_id'] = 'character.reply.v99'
            if mutation == 'inverse': value['turns'][0]['ledger_inverse']['added_entry_ids'] = []
            if mutation == 'v1_annotation': value['requests'][0]['attempts'][0]['reply_contract_id'] = V1
            if mutation == 'ai_statement':
                source = value['ledger'][0]['source']; reply = value['turns'][0]['ai_message']
                source['message_ids'] = [reply['message_id']]
                source['evidence'] = [{'message_id': reply['message_id'], 'quote': reply['content']}]
            with self.subTest(mutation=mutation), self.assertRaises(CharacterSessionError): self.repo.save(value, expected_revision=baseline['revision'])
            self.assertEqual(baseline, self.value())

    async def test_all_explicit_annotation_sources_must_be_user_and_capacity_guards(self):
        begun = self.begin(); job = self.service.jobs[begun['job']['request_id']]
        raw = self.transport.response(job['plan'])
        data = json.loads(job['plan'].user_prompt)
        raw['ledger_ops'][0]['source']['message_ids'].append(data['current_ai_message_id'])
        raw['ledger_ops'][0]['source']['evidence'].append({'message_id': data['current_ai_message_id'], 'quote': '自然回应'})
        self.transport.raw = json.dumps(raw)
        result = await self.service.execute(begun['job']['request_id'], lambda *_: None)
        self.assertEqual('CONTRACT_INVALID', result['error_code']); self.assertEqual([], self.value()['ledger'])
        self.transport.raw = None
        result = await self.send(); eid = self.value()['ledger'][0]['entry_id']
        value = self.value(); roots = [str(uuid4()) for _ in range(128)]
        value['extensions']['character_memory']['dismissed_auto_root_ids'] = roots
        old = value['revision']; value['revision'] += 1; self.repo.save(value, expected_revision=old)
        with self.assertRaises(CharacterSessionError) as exc: self.update('selection', eid, True)
        self.assertEqual('MEMORY_DISMISS_LIMIT', exc.exception.code)
        self.update('release', roots[0]); self.update('selection', eid, True)
        self.assertEqual(128, len(settings(self.value())['dismissed_auto_root_ids']))

    async def test_v2_six_ops_and_duplicates_inverse_atomic_failure(self):
        begun = self.begin(); raw = self.transport.response(self.service.jobs[begun['job']['request_id']]['plan'])
        raw['ledger_ops'] *= 6
        raw['memory_annotations'] = [{'op_index': i, 'reason': 'explicit_boundary'} for i in range(6)]
        self.transport.raw = json.dumps(raw)
        result = await self.service.execute(begun['job']['request_id'], lambda *_: None)
        self.assertEqual('committed', result['status']); self.assertEqual(6, len(self.value()['ledger']))
        self.assertEqual(1, len(result['memory_notice']['entry_ids']))
        self.assertEqual(6, len(self.value()['turns'][0]['ledger_inverse']['added_entry_ids']))
        before = self.value()
        begun = self.begin(); self.transport.raw = json.dumps(self.transport.response(self.service.jobs[begun['job']['request_id']]['plan']))
        real_replace = __import__('os').replace; count = 0
        def fail_commit_once(src, dst):
            nonlocal count
            count += 1
            if count == 1: raise OSError('synthetic commit failure')
            return real_replace(src, dst)
        with patch('core.character_chat.repository.os.replace', side_effect=fail_commit_once):
            result = await self.service.execute(begun['job']['request_id'], lambda *_: None)
        self.assertEqual('failed', result['status']); self.assertNotIn('memory_notice', result)
        self.assertEqual(before['ledger'], self.value()['ledger']); self.assertEqual(before['turns'], self.value()['turns'])


class M2RouteTests(unittest.TestCase):
    setUp = route_fixtures.CharacterRouteTests.setUp
    def test_strict_api_fields_enable_and_notice_ack(self):
        self.service.transport = AnnotationTransport()
        url = self.prefix + '/' + self.sid
        for enabled in (False, 1, None):
            self.assertEqual(400, self.client.put(url + '/memory/automatic', json={'expected_revision': 0, 'enabled': enabled}).status_code)
        self.assertEqual(200, self.client.put(url + '/memory/automatic', json={'expected_revision': 0, 'enabled': True}).status_code)
        result = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send', 'delivery': 'non_stream', 'content': '不要擅自决定'}).json()
        eid = result['memory_notice']['entry_ids'][0]
        payload = {'expected_revision': 1, 'entry_id': eid, 'dismissed': True}
        for changes in ({'dismissed': 1}, {'extra': 0}, {'expected_revision': True}, {'entry_id': str(uuid4())}):
            self.assertEqual(400, self.client.put(url + '/memory/automatic-selection', json={**payload, **changes}).status_code)
        response = self.client.put(url + '/memory/automatic-selection', json=payload)
        self.assertEqual(200, response.status_code); self.assertEqual({'session_id', 'revision', 'memory_settings'}, set(response.json()))
        self.assertEqual(409, self.client.put(url + '/memory/automatic-selection', json=payload).status_code)
        self.assertEqual(400, self.client.post(url + '/memory/automatic-selection/release', json={'expected_revision': 2, 'root_entry_id': eid}).status_code)
        ack = {'expected_revision': 2, 'action_id': result['action_id']}
        self.assertEqual(400, self.client.put(url + '/memory/notice-ack', json={**ack, 'notice_ack_revision': 999}).status_code)
        self.assertEqual(200, self.client.put(url + '/memory/notice-ack', json=ack).status_code)
        self.assertEqual(1, self.client.get(url).json()['memory_settings']['notice_ack_revision'])
