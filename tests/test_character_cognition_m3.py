import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.cognition import index_entries, public_index
from core.character_chat.context import build_context
from core.character_chat.context_contract import LEGACY, M3, context_contract
from core.character_chat.contract import plan_turn
from core.character_chat.errors import retryable
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.recall import recall_candidates, close_groups, trim_group, public_report, MESSAGE_FIELDS
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from core.character_chat.transport import CharacterTransport
from core.prompt_studio import SLICES, ModelRequestPlan, PromptOverrideStore, compose_prompt
from tests.test_character_memory import fixture, pending
from tests.test_character_chat_lifecycle import FakeTransport
from tests import test_character_chat_routes as route_fixtures


def linked(value, index, refs, content='coffee 海边'):
    entry = value['ledger'][index]
    entry['content'] = content
    entry['source'] = {'type': 'player_statement', 'message_ids': [m['message_id'] for m in refs],
                       'evidence': [{'message_id': m['message_id'], 'quote': m['content'][:100]} for m in refs]}
    return entry


class CognitionTests(unittest.TestCase):
    def test_public_whitelist_and_readonly(self):
        value = fixture(4)
        value['ledger'][0]['about_instance_id'] = value['turns'][0]['user_message']['speaker_instance_id']
        value['ledger'][0]['memory_annotation'] = {'reason': 'explicit_boundary'}
        value['ledger'][1]['visibility']['audience_instance_ids'] = [value['ledger'][1]['subject_instance_id']]
        value['ledger'][2]['status'] = 'superseded'
        value['ledger'][3]['source'] = {'type': 'author', 'message_ids': [], 'evidence': []}
        before = copy.deepcopy(value)
        result = public_index(value)
        self.assertEqual(2, len(result['entries']))
        self.assertEqual({'entry_id', 'about_instance_id', 'kind', 'basis', 'root_entry_id', 'supersedes_entry_id', 'annotation_reason'}, set(result['entries'][0]))
        self.assertEqual('author', result['entries'][1]['basis'])
        self.assertEqual('explicit_boundary', result['entries'][0]['annotation_reason'])
        self.assertNotIn(value['ledger'][1]['entry_id'], json.dumps(result))
        self.assertNotIn('content', json.dumps(result)); self.assertEqual(before, value)

    def test_invalid_formal_visibility_quote_subject_and_chain_are_excluded(self):
        mutations = [lambda v: v['turns'].pop(0),
                     lambda v: v['ledger'][0]['source']['message_ids'].__setitem__(0, str(uuid4())),
                     lambda v: v['ledger'][0]['source']['evidence'][0].update(quote='不存在的引文'),
                     lambda v: v['turns'][0]['user_message']['visibility'].update(audience_instance_ids=[v['ledger'][0]['subject_instance_id']]),
                     lambda v: v['ledger'][0].update(subject_instance_id=v['turns'][0]['user_message']['speaker_instance_id']),
                     lambda v: v['ledger'][0].update(supersedes_entry_id=v['ledger'][0]['entry_id'])]
        for mutate in mutations:
            value = fixture(2); eid = value['ledger'][0]['entry_id']; mutate(value)
            self.assertNotIn(eid, [r['entry_id'] for r in index_entries(value)])

    def test_supersede_root_current_only_and_invalid_identity(self):
        value = fixture(3); old, new, latest = value['ledger']
        old['status'] = new['status'] = 'superseded'
        new['supersedes_entry_id'] = old['entry_id']; latest['supersedes_entry_id'] = new['entry_id']
        rows = public_index(value)['entries']
        self.assertEqual(1, len(rows)); self.assertEqual(old['entry_id'], rows[0]['root_entry_id'])
        self.assertEqual(new['entry_id'], rows[0]['supersedes_entry_id'])
        new['kind'] = 'belief'; self.assertEqual([], index_entries(value))


class RecallTests(unittest.TestCase):
    def test_old_source_actual_input_whitelist_and_same_final_evidence(self):
        value = fixture(25); old = value['turns'][0]['user_message']; old['private_extension'] = 'not projected'
        plan, allowed, ids, report = build_context(value, pending('ＣＯＦＦＥＥ 海边'))
        data = json.loads(plan.user_prompt)
        self.assertEqual(M3, data['context_contract_id']); self.assertEqual(M3, plan.context_contract_id)
        self.assertEqual([old['message_id']], [m['message_id'] for m in data['recalled_sources']])
        self.assertEqual(set(MESSAGE_FIELDS), set(data['recalled_sources'][0]))
        self.assertEqual({m['message_id'] for m in data['history'] + data['recalled_sources']}, {m['message_id'] for m in allowed})
        self.assertEqual({e['entry_id'] for e in data['ledger']}, ids)
        self.assertEqual({'version': 1, 'entries': [{'entry_id': value['ledger'][0]['entry_id'], 'state': 'sent'}]}, report['source_recall'])
        self.assertTrue(all(m['contextContractId'] == M3 for m in plan.prompt_manifest))

    def test_legacy_projection_and_zero_overlap_never_recalls(self):
        value = fixture(25)
        plan, allowed, _, report = build_context(value, pending('coffee'), context_contract_id=LEGACY)
        data = json.loads(plan.user_prompt)
        self.assertNotIn('recalled_sources', data); self.assertNotIn('context_contract_id', data)
        self.assertNotIn('source_recall', report)
        self.assertNotIn(value['turns'][0]['user_message']['message_id'], [m['message_id'] for m in allowed])
        for query in ('我', 'coffees', 'totallyunrelated'):
            plan, _, _, report = build_context(value, pending(query))
            self.assertEqual([], json.loads(plan.user_prompt)['recalled_sources']); self.assertEqual([], report['source_recall']['entries'])

    def test_no_unlinked_history_author_or_recent_source_search(self):
        value = fixture(25); value['ledger'] = value['ledger'][1:]
        self.assertEqual([], recall_candidates(value, value['ledger'], 'coffee', []))
        entry = value['ledger'][0]; entry['content'] = 'coffee'; entry['source'] = {'type': 'author', 'message_ids': [], 'evidence': []}
        self.assertEqual([], recall_candidates(value, [entry], 'coffee', []))
        value = fixture(1)
        self.assertEqual([], recall_candidates(value, value['ledger'], 'coffee', [value['turns'][0]['user_message']]))

    def test_four_message_whole_group_limit_skips_then_continues(self):
        value = fixture(8); messages = [t['user_message'] for t in value['turns']]
        for i, refs in enumerate(([messages[0], messages[1]], [messages[2]], [messages[3], messages[4]], [messages[5]])):
            linked(value, i, refs)
        ledger = value['ledger'][:4]; groups = recall_candidates(value, ledger, 'coffee', [])
        recalled = close_groups(groups, [], ledger)
        self.assertEqual([messages[i]['message_id'] for i in (0, 1, 2, 5)], [m['message_id'] for m in recalled])
        self.assertEqual(['sent', 'sent', 'limit', 'sent'], [r['state'] for r in public_report(groups)['entries']])

    def test_4000_unicode_chars_complete_not_truncated_and_no_refill(self):
        value = fixture(4); messages = [t['user_message'] for t in value['turns']]
        for m, size in zip(messages, (4001, 3999, 2, 1)): m['content'] = '😀' * size
        for i, m in enumerate(messages): linked(value, i, [m])
        groups = recall_candidates(value, value['ledger'], 'coffee', [])
        recalled = close_groups(groups, [], value['ledger'])
        self.assertEqual([3999, 1], [len(m['content']) for m in recalled])
        self.assertEqual(['limit', 'sent', 'limit', 'sent'], [r['state'] for r in public_report(groups)['entries']])
        trim_group(groups); close_groups(groups, [], value['ledger'])
        self.assertFalse(groups[2]['active']); self.assertEqual('limit', public_report(groups)['entries'][2]['state'])

    def test_shared_sources_group_trimming_and_orphan_parent_removal(self):
        value = fixture(3); m = value['turns'][0]['user_message']
        for i in range(3): linked(value, i, [m])
        groups = recall_candidates(value, value['ledger'], 'coffee', [])
        self.assertEqual(1, len(close_groups(groups, [], value['ledger'])))
        trim_group(groups); self.assertEqual(1, len(close_groups(groups, [], value['ledger'])))
        trim_group(groups); self.assertEqual(1, len(close_groups(groups, [], value['ledger'])))
        self.assertEqual([], close_groups(groups, [], value['ledger'][1:]))
        self.assertEqual(['budget'] * 3, [r['state'] for r in public_report(groups)['entries']])

    def test_initial_history_loss_breaks_complete_group_never_dynamic_adds(self):
        value = fixture(3); old, recent = [t['user_message'] for t in value['turns'][:2]]
        entry = linked(value, 0, [old, recent])
        groups = recall_candidates(value, [entry], 'coffee', [recent])
        self.assertEqual([old['message_id']], [m['message_id'] for m in close_groups(groups, [recent], [entry])])
        self.assertEqual([], close_groups(groups, [], [entry]))
        self.assertEqual('budget', public_report(groups)['entries'][0]['state'])

    def test_shared_source_retains_first_selection_order_after_parent_removed(self):
        value = fixture(4); messages = [t['user_message'] for t in value['turns']]
        for i, refs in enumerate(([messages[0], messages[1]], [messages[2]], [messages[1], messages[3]])):
            linked(value, i, refs)
        groups = recall_candidates(value, value['ledger'][:3], 'coffee', [])
        recalled = close_groups(groups, [], value['ledger'][1:3])
        self.assertEqual([messages[i]['message_id'] for i in (1, 2, 3)], [m['message_id'] for m in recalled])

    def test_private_support_has_no_public_report_and_no_sneak_partial_group(self):
        value = fixture(3); messages = [t['user_message'] for t in value['turns']]
        linked(value, 0, [messages[0]])['visibility']['audience_instance_ids'] = [value['ledger'][0]['subject_instance_id']]
        linked(value, 1, [messages[0], messages[1]])
        messages[1]['content'] = 'x' * 4001; value['ledger'][1]['source']['evidence'][1]['quote'] = 'x'
        groups = recall_candidates(value, value['ledger'][:2], 'coffee', [])
        self.assertEqual(1, len(close_groups(groups, [], value['ledger'][:2])))
        self.assertEqual([{'entry_id': value['ledger'][1]['entry_id'], 'state': 'limit'}], public_report(groups)['entries'])

    def test_budget_removes_recall_before_recent_turns_and_parent_ids_agree(self):
        value = fixture(25); sizes = []
        def budget(_, raw, **kwargs):
            data = json.loads(raw); sizes.append((len(data['history']), len(data['recalled_sources'])))
            return {'fits': not data['recalled_sources']}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            plan, allowed, ids, report = build_context(value, pending('coffee'))
        self.assertEqual([(40, 1), (40, 0)], sizes)
        self.assertEqual('budget', report['source_recall']['entries'][0]['state'])
        self.assertEqual([], json.loads(plan.user_prompt)['recalled_sources'])
        self.assertEqual(40, len(allowed)); self.assertEqual(25, len(ids))

    def test_budget_shared_sources_does_not_claim_payload_shrunk_until_last_support(self):
        value = fixture(25); old = value['turns'][0]['user_message']
        for i in range(3): linked(value, i, [old])
        sizes = []
        def budget(_, raw, **kwargs):
            data = json.loads(raw); sizes.append((len(data['history']), len(data['recalled_sources'])))
            return {'fits': not data['recalled_sources']}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            _, _, _, report = build_context(value, pending('coffee'))
        self.assertEqual([(40, 1), (40, 1), (40, 1), (40, 0)], sizes)
        self.assertEqual(['budget'] * 3, [r['state'] for r in report['source_recall']['entries']])

    def test_illegal_nonformal_frozen_evidence_and_old_dialogue_event_rejected(self):
        value = fixture(25); p = pending('coffee'); plan, allowed, ids, _ = build_context(value, p)
        old = value['turns'][0]['user_message']
        op = {'op': 'add', 'kind': 'knowledge', 'content': '旧源修订', 'source': {'type': 'player_statement',
              'message_ids': [old['message_id']], 'evidence': [{'message_id': old['message_id'], 'quote': old['content'][:100]}]},
              'visibility': copy.deepcopy(old['visibility'])}
        def result(): return json.dumps({'reply': '好的', 'ledger_ops': [op]})
        action, attempt = {'action_id': str(uuid4())}, {'request_id': str(uuid4()), 'pending_input': p, 'base_revision': value['revision']}
        candidate, _ = plan_turn(value, action, attempt, result(), allowed, ids)
        self.assertEqual(old['message_id'], candidate['ledger'][-1]['source']['message_ids'][0])
        for mutate in ('old_event', 'tamper', 'missing', 'arbitrary_target'):
            raw = result(); evidence = copy.deepcopy(allowed)
            if mutate == 'old_event':
                obj = json.loads(raw); obj['ledger_ops'][0]['source']['type'] = 'dialogue_event'; raw = json.dumps(obj)
            elif mutate == 'tamper': evidence[-1]['content'] = 'tampered'
            elif mutate == 'missing': evidence = [m for m in evidence if m['message_id'] != old['message_id']]
            else:
                obj = json.loads(raw); obj['ledger_ops'][0].update(op='supersede', target_entry_id=value['ledger'][0]['entry_id']); raw = json.dumps(obj)
            with self.assertRaises(CharacterSessionError) as caught:
                plan_turn(value, action, attempt, raw, evidence, ids - {value['ledger'][0]['entry_id']} if mutate == 'arbitrary_target' else ids)
            self.assertEqual('CONTRACT_INVALID', caught.exception.code)


class CognitionRoutesTests(unittest.TestCase):
    setUp = route_fixtures.CharacterRouteTests.setUp

    def test_index_no_store_strict_read_and_file_unchanged(self):
        url = self.prefix + '/' + self.sid
        self.transport.with_ledger = True
        response = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'delivery': 'non_stream', 'content': '合成 coffee'})
        self.assertEqual('committed', response.json()['status'])
        files = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in Path(self.temp.name).rglob('*.json')}
        endpoint = url + '/memory/cognition'; result = self.client.get(endpoint)
        self.assertEqual(200, result.status_code); self.assertEqual('no-store', result.headers['cache-control'])
        self.assertEqual(1, result.json()['revision']); self.assertEqual(1, len(result.json()['entries']))
        self.assertEqual(files, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files})
        for response in (self.client.get(endpoint + '?view=spoiler'), self.client.request('GET', endpoint, json={'query': 'coffee'})):
            self.assertEqual(400, response.status_code); self.assertEqual('no-store', response.headers['cache-control'])

    def test_bad_old_data_unknown_schema_and_context_fail_closed(self):
        url = self.prefix + '/' + self.sid
        self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'delivery': 'non_stream', 'content': 'coffee'})
        saved = self.repo.load(self.sid); before = self.transport.calls
        for mode, status, code in (('context', 409, 'CONTEXT_CONTRACT_UNSUPPORTED'),
                                   ('corrupt', 500, 'SESSION_CORRUPT'), ('schema', 409, 'SCHEMA_READ_ONLY')):
            value = copy.deepcopy(saved)
            if mode == 'context': value['requests'][0]['attempts'][0]['context_contract_id'] = 'unknown'
            elif mode == 'corrupt': value['turns'][0]['user_message']['content'] = ''
            else: value['schema_version'] = 2
            with patch.object(self.repo, '_load', return_value=value):
                response = self.client.get(url + '/memory/cognition')
            self.assertEqual(status, response.status_code, response.text)
            self.assertEqual(code, response.json()['error']['code']); self.assertEqual('no-store', response.headers['cache-control'])
        self.assertEqual(before, self.transport.calls)


class ContextVersionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name)); self.transport = FakeTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        legacy = create_session(str(uuid4()), {'name': '合成', 'description': '固定合成底稿'}, {'kind': 'character', 'key': '合成'})
        legacy['extensions'].pop('character_memory'); self.sid = self.repo.create(legacy)['session_id']

    def begin(self, **extra):
        value = self.repo.load(self.sid)
        retry_action_id = extra.pop('retry_action_id', None)
        if retry_action_id:
            action = next(a for a in value['requests'] if a['action_id'] == retry_action_id)
            return self.service.begin(self.sid, {'expected_revision': value['revision'], 'delivery': 'non_stream',
                'retry_of': action['attempts'][-1]['request_id'], 'retry_token': str(uuid4())}, retry_action_id=retry_action_id)
        payload = {'client_action_id': str(uuid4()), 'expected_revision': value['revision'],
                   'operation': 'send', 'delivery': 'non_stream', 'content': 'coffee', **extra}
        if payload['operation'] != 'send': payload.pop('content')
        return self.service.begin(self.sid, payload)

    async def test_new_legacy_reply_independent_versions_retry_and_regenerate(self):
        job = self.begin()['job']; value = self.repo.load(self.sid)
        attempt = value['requests'][0]['attempts'][0]
        self.assertEqual(M3, attempt['context_contract_id']); self.assertEqual('character.reply.v1', attempt['reply_contract_id'])
        self.transport.raw = 'bad'; failed = await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual('failed', failed['status'])
        action = self.repo.load(self.sid)['requests'][0]
        self.assertEqual(M3, action['retry_input']['context_contract_id'])
        retry = self.begin(operation='retry', retry_action_id=action['action_id'])
        self.transport.raw = None; result = await self.service.execute(retry['job']['request_id'], lambda *_: None)
        self.assertEqual('committed', result['status']); self.assertIn('source_recall_report', result)
        self.assertEqual('character.reply.v1', self.transport.plans[-1].contract_id)
        regen = self.begin(operation='regenerate', target_turn_id=result['turn_id'])
        result = await self.service.execute(regen['job']['request_id'], lambda *_: None)
        self.assertEqual('committed', result['status']); self.assertEqual(M3, self.transport.plans[-1].context_contract_id)
        self.assertNotIn('character_memory', self.repo.load(self.sid)['extensions'])

    async def test_old_pending_startup_interruption_preserves_legacy_no_call(self):
        self.begin()
        self.repo.transaction(self.sid, lambda v: (v['requests'][0]['attempts'][0].pop('context_contract_id'), True))
        restarted = CharacterChatService(self.repo, self.transport)
        action = self.repo.load(self.sid)['requests'][0]
        self.assertEqual('interrupted', action['attempts'][0]['status'])
        self.assertEqual(LEGACY, context_contract(action['attempts'][0])); self.assertEqual(LEGACY, action['retry_input']['context_contract_id'])
        self.assertEqual(0, self.transport.calls)
        self.service = restarted
        retried = self.begin(operation='retry', retry_action_id=action['action_id'])
        await self.service.execute(retried['job']['request_id'], lambda *_: None)
        self.assertEqual(M3, self.transport.plans[-1].context_contract_id)

    async def test_unknown_context_save_and_transport_fail_before_provider(self):
        self.begin(); before = self.repo.load(self.sid)
        for invalid in ('character.context.future', None, True, 1):
            with self.assertRaises(CharacterSessionError) as caught:
                self.repo.transaction(self.sid, lambda v: (v['requests'][0]['attempts'][0].update(context_contract_id=invalid), True))
            self.assertEqual('CONTEXT_CONTRACT_UNSUPPORTED', caught.exception.code)
            self.assertFalse(retryable(caught.exception.code)); self.assertEqual(before, self.repo.load(self.sid))
        plan = ModelRequestPlan('sys', '{}', [], .8, None, 'character.reply', 'json', 'character.reply.v1', 'future')
        with patch('core.character_chat.transport.AsyncOpenAI') as provider:
            with self.assertRaises(CharacterSessionError) as caught:
                await CharacterTransport().generate({}, plan, {'fits': True}, 'non_stream', lambda *_: None)
            self.assertEqual('CONTEXT_CONTRACT_UNSUPPORTED', caught.exception.code); provider.assert_not_called()

    async def test_persisted_unknown_context_blocks_new_actions_and_recovery_zero_call(self):
        self.begin(); unknown = self.repo.load(self.sid)
        unknown['requests'][0]['attempts'][0]['context_contract_id'] = 'character.context.future'
        # Only this temporary synthetic repository bypasses validation to represent a future save.
        with patch('core.character_chat.repository.validate_session'):
            self.repo._write(unknown)
        path = self.repo.directory / (self.sid + '.json')
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with patch.object(self.repo, '_write') as write:
            with self.assertRaises(CharacterSessionError) as caught: self.repo.load(self.sid)
            self.assertEqual('CONTEXT_CONTRACT_UNSUPPORTED', caught.exception.code)
            with self.assertRaises(CharacterSessionError) as caught:
                self.service.begin(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': 0,
                    'operation': 'send', 'delivery': 'non_stream', 'content': 'coffee'})
            self.assertEqual('CONTEXT_CONTRACT_UNSUPPORTED', caught.exception.code)
            CharacterChatService(self.repo, self.transport)
            write.assert_not_called()
        self.assertEqual(0, self.transport.calls)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    async def test_context_over_budget_all_false_has_zero_provider_and_no_pending(self):
        with patch('core.character_chat.context.budget_report', return_value={'fits': False}):
            with self.assertRaises(CharacterSessionError) as caught: self.begin()
        self.assertEqual('CONTEXT_LIMIT', caught.exception.code); self.assertEqual(0, self.transport.calls)
        action = self.repo.load(self.sid)['requests'][0]
        self.assertEqual('failed', action['attempts'][0]['status'])

    async def test_old_source_commit_report_undo_and_cancel_failure_atomic(self):
        self.transport.with_ledger = True
        first = self.begin()['job']; await self.service.execute(first['request_id'], lambda *_: None)
        self.transport.with_ledger = False
        for _ in range(21):
            job = self.begin(content='ordinary filler')['job']; await self.service.execute(job['request_id'], lambda *_: None)
        value = self.repo.load(self.sid); old = value['turns'][0]['user_message']; root = value['ledger'][0]['entry_id']
        op = {'op': 'supersede', 'target_entry_id': root, 'kind': 'knowledge', 'content': 'coffee 新限定',
              'source': {'type': 'player_statement', 'message_ids': [old['message_id']],
                         'evidence': [{'message_id': old['message_id'], 'quote': old['content']}]}, 'visibility': old['visibility']}
        self.transport.raw = json.dumps({'reply': '好的', 'ledger_ops': [op]})
        job = self.begin()['job']; events = []
        result = await self.service.execute(job['request_id'], lambda event, data: events.append((event, data)))
        self.assertEqual('committed', result['status'])
        self.assertEqual(result['source_recall_report'], events[0][1]['source_recall_report'])
        self.assertEqual('sent', result['source_recall_report']['entries'][0]['state'])
        self.assertNotIn('source_recall_report', json.dumps(self.repo.load(self.sid)))
        self.begin(operation='undo', target_turn_id=result['turn_id'])
        value = self.repo.load(self.sid); self.assertEqual('active', value['ledger'][0]['status']); self.assertEqual(1, len(value['ledger']))
        job = self.begin()['job']; calls = self.transport.calls
        self.service.cancel(self.sid, job['request_id'])
        await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual(calls, self.transport.calls); self.assertEqual(1, len(self.repo.load(self.sid)['ledger']))
        job = self.begin()['job']
        with patch.object(self.repo, '_write', side_effect=CharacterSessionError('PERSISTENCE_FAILED')):
            failed = await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual('PERSISTENCE_FAILED', failed['error_code'])
        self.assertEqual(1, len(self.repo.load(self.sid)['ledger']))

    def test_new_prompt_tasks_independent_readonly_contract_and_visible_old(self):
        ids = {s.id: s for s in SLICES}
        for version in (1, 2):
            prefix = f'character.reply.m3.v{version}'
            self.assertTrue(ids[prefix + '.core'].editable)
            self.assertFalse(ids[prefix + '.contract'].editable); self.assertFalse(ids[prefix + '.presentation'].editable)
            self.assertIn('旧v1/v2 core覆盖未自动应用', ids[prefix + '.core'].description)
        self.assertIn('character.reply.core', ids); self.assertIn('character.reply.v2.core', ids)

    def test_old_core_override_is_not_injected_into_new_m3(self):
        store = PromptOverrideStore(Path(self.temp.name) / 'synthetic-overrides.json')
        store.save('character.reply.core', 'OLD_V1_SYNTHETIC_OVERRIDE')
        store.save('character.reply.v2.core', 'OLD_V2_SYNTHETIC_OVERRIDE')
        for version in (1, 2):
            system = compose_prompt(f'character.reply.m3.v{version}', {'character.presentation_mode': 'messenger'}, store=store)
            self.assertNotIn('SYNTHETIC_OVERRIDE', system.text)
            self.assertTrue(all(m['source'] != 'override' for m in system.manifest))
