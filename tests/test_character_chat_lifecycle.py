import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService, action_by_id, action_view, session_view
from core.character_chat.contract import public_ledger, parse_result
from core.character_chat.context import build_context
from core.character_chat.stream_json import ReplyPreview


class FakeTransport:
    def __init__(self):
        self.calls = 0
        self.raw = None
        self.gate = None
        self.started = None
        self.with_ledger = False
        self.supersede = False
        self.plans = []

    def snapshot(self):
        return {'model': 'synthetic', 'budget_options': {}}

    async def generate(self, config, plan, report, delivery, emit):
        self.calls += 1
        self.plans.append(plan)
        data = json.loads(plan.user_prompt)
        if self.started:
            self.started.set()
        if self.gate:
            await self.gate.wait()
        if self.raw is not None:
            return self.raw
        reply = '回应：' + data['current_user_message']['content']
        emit(reply[:2])
        ops = []
        if self.with_ledger:
            ids = [p['instance_id'] for p in data['participants']]
            mid = data['current_user_message']['message_id']
            op = {'op': 'add', 'kind': 'knowledge', 'content': '收到陈述：' + data['current_user_message']['content'],
                  'source': {'type': 'player_statement', 'message_ids': [mid],
                             'evidence': [{'message_id': mid, 'quote': data['current_user_message']['content']}]},
                  'visibility': {'audience_instance_ids': ids}}
            if self.supersede:
                op.update(op='supersede', target_entry_id=data['ledger'][0]['entry_id'])
            ops.append(op)
        return json.dumps({'reply': reply, 'ledger_ops': ops}, ensure_ascii=False)


class CharacterLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))
        self.transport = FakeTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        self.session = self.repo.create(create_session(str(uuid4()), {'name': '合成角色', 'description': '合成固定底稿'},
            {'kind': 'character', 'key': '合成角色'}))
        self.sid = self.session['session_id']

    def begin(self, *, operation='send', content='合成输入', target=None, aid=None, revision=None):
        payload = {'client_action_id': aid or str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'] if revision is None else revision,
                   'operation': operation, 'delivery': 'stream'}
        if operation == 'send':
            payload['content'] = content
        else:
            payload['target_turn_id'] = target
        return self.service.begin(self.sid, payload), payload

    async def send(self, **kwargs):
        result, payload = self.begin(**kwargs)
        if 'job' in result:
            result = await self.service.execute(result['job']['request_id'], lambda *_: None)
        else:
            result = result['existing']
        return result, payload

    def assert_code(self, code, fn):
        with self.assertRaises(CharacterSessionError) as caught:
            fn()
        self.assertEqual(code, caught.exception.code)

    async def test_atomic_turn_and_duplicate_action_no_extra_call(self):
        result, payload = await self.send()
        value = self.repo.load(self.sid)
        self.assertEqual(1, value['revision'])
        self.assertEqual(1, len(value['turns']))
        self.assertEqual('committed', result['status'])
        duplicate = self.service.begin(self.sid, payload)
        self.assertEqual(result['request_id'], duplicate['existing']['request_id'])
        self.assertEqual(1, self.transport.calls)
        changed = dict(payload, content='不同输入')
        self.assert_code('IDEMPOTENCY_MISMATCH', lambda: self.service.begin(self.sid, changed))

    async def test_twice_regenerate_then_undo_archives_to_original_actions(self):
        first, _ = await self.send()
        second, _ = await self.send(operation='regenerate', target=first['turn_id'])
        third, _ = await self.send(operation='regenerate', target=second['turn_id'])
        undo, _ = await self.send(operation='undo', target=third['turn_id'])
        value = self.repo.load(self.sid)
        self.assertEqual([], value['turns'])
        self.assertEqual(4, value['revision'])
        for result, state in ((first, 'replaced'), (second, 'replaced'), (third, 'withdrawn')):
            action = action_by_id(value, result['action_id'])
            self.assertEqual(state, action['result_state'])
            self.assertEqual(result['turn_id'], action['archived_turn']['turn_id'])
            self.assertEqual('committed', action['attempts'][0]['status'])
            self.assertNotIn('turn', action_view(value, action))
        self.assertNotIn('archived_turn', action_by_id(value, undo['action_id']))
        self.assertEqual(3, self.transport.calls)

    async def test_ledger_supersede_and_undo_exact_inverse(self):
        self.transport.with_ledger = True
        await self.send(content='第一条陈述')
        prior = copy.deepcopy(self.repo.load(self.sid)['ledger'])
        self.transport.supersede = True
        second, _ = await self.send(content='修正后的陈述')
        ledger = self.repo.load(self.sid)['ledger']
        self.assertEqual(['superseded', 'active'], [e['status'] for e in ledger])
        await self.send(operation='undo', target=second['turn_id'])
        self.assertEqual(prior, self.repo.load(self.sid)['ledger'])

    async def test_invalid_reply_whole_turn_failed_retry_token_idempotent(self):
        self.transport.raw = '{"reply":"未提交", "ledger_ops":[]}garbage'
        result, payload = await self.send()
        self.assertEqual('failed', result['status'])
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        retry = {'expected_revision': 0, 'retry_of': result['request_id'], 'retry_token': str(uuid4()), 'delivery': 'non_stream'}
        self.transport.raw = None
        started = self.service.begin(self.sid, retry, retry_action_id=payload['client_action_id'])
        duplicate = self.service.begin(self.sid, retry, retry_action_id=payload['client_action_id'])
        self.assertEqual(started['job']['request_id'], duplicate['existing']['request_id'])
        done = await self.service.execute(started['job']['request_id'], lambda *_: None)
        self.assertEqual('committed', done['status'])
        new_retry = dict(retry, retry_token=str(uuid4()), retry_of=done['request_id'], expected_revision=1)
        self.assert_code('STALE_RETRY', lambda: self.service.begin(self.sid, new_retry, retry_action_id=payload['client_action_id']))
        self.assertEqual(2, self.transport.calls)

    async def test_pending_busy_delete_and_cancel_before_call(self):
        started, payload = self.begin()
        rid = started['job']['request_id']
        self.assert_code('SESSION_BUSY', lambda: self.begin())
        self.assert_code('SESSION_BUSY', lambda: self.repo.delete(self.sid, expected_revision=0))
        cancelled = self.service.cancel(self.sid, rid)
        self.assertEqual('cancelled', cancelled['status'])
        done = await self.service.execute(rid, lambda *_: None)
        self.assertEqual('cancelled', done['status'])
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], self.repo.load(self.sid)['turns'])

    async def test_cancel_during_network_and_commit_wins_order(self):
        self.transport.gate, self.transport.started = asyncio.Event(), asyncio.Event()
        started, _ = self.begin()
        rid = started['job']['request_id']
        task = asyncio.create_task(self.service.execute(rid, lambda *_: None))
        await self.transport.started.wait()
        self.service.cancel(self.sid, rid)
        done = await task
        self.assertEqual('cancelled', done['status'])
        self.transport.gate = None
        committed, _ = await self.send()
        late = self.service.cancel(self.sid, committed['request_id'])
        self.assertEqual('already_committed', late['cancel_result'])
        self.assertEqual(1, len(self.repo.load(self.sid)['turns']))

    async def test_pending_write_failure_zero_model_call(self):
        with patch('core.character_chat.repository.os.replace', side_effect=OSError('synthetic')):
            self.assert_code('PERSISTENCE_FAILED', lambda: self.begin())
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], self.repo.load(self.sid)['requests'])

    async def test_commit_failure_preserves_history_blocks_when_terminal_also_fails(self):
        started, _ = self.begin()
        with patch('core.character_chat.repository.os.replace', side_effect=OSError('synthetic')):
            done = await self.service.execute(started['job']['request_id'], lambda *_: None)
        self.assertEqual('PERSISTENCE_FAILED', done['error_code'])
        self.assertEqual([], self.repo.load(self.sid)['turns'])
        self.assertEqual(0, self.repo.load(self.sid)['revision'])
        self.assert_code('PERSISTENCE_FAILED', lambda: self.begin())

    async def test_commit_write_failure_terminal_write_succeeds_no_half_turn(self):
        import os
        original_replace = os.replace
        calls = 0
        def fail_once(source, target):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('synthetic commit failure')
            return original_replace(source, target)
        started, _ = self.begin()
        with patch('core.character_chat.repository.os.replace', side_effect=fail_once):
            done = await self.service.execute(started['job']['request_id'], lambda *_: None)
        value = self.repo.load(self.sid)
        self.assertEqual('failed', done['status'])
        self.assertEqual([], value['turns'])
        self.assertEqual([], value['ledger'])
        self.assertEqual(0, value['revision'])
        self.assertEqual('failed', value['requests'][0]['attempts'][0]['status'])
        self.assertNotIn(self.sid, self.service.blocked)

    async def test_bad_ledger_source_or_visibility_rejects_entire_turn(self):
        original_generate = self.transport.generate
        self.transport.with_ledger = True
        for violation in ('quote', 'message', 'audience', 'inference', 'unknown', 'badtype'):
            async def invalid(config, plan, report, delivery, emit):
                raw = await original_generate(config, plan, report, delivery, emit)
                value = json.loads(raw)
                op = value['ledger_ops'][0]
                if violation == 'quote':
                    op['source']['evidence'][0]['quote'] = '不存在的引文'
                elif violation == 'message':
                    op['source']['message_ids'] = [str(uuid4())]
                elif violation == 'audience':
                    op['visibility']['audience_instance_ids'] = [str(uuid4())]
                elif violation == 'inference':
                    op['source']['type'] = 'model_inference'
                elif violation == 'unknown':
                    op['subject_instance_id'] = self.session['participants'][0]['instance_id']
                else:
                    op['visibility']['audience_instance_ids'] = [{}]
                return json.dumps(value, ensure_ascii=False)
            self.transport.generate = invalid
            result, _ = await self.send()
            self.assertEqual('CONTRACT_INVALID', result['error_code'], violation)
            value = self.repo.load(self.sid)
            self.assertEqual([], value['turns'])
            self.assertEqual([], value['ledger'])
            self.assertEqual(0, value['revision'])

    async def test_restart_recovery_preserves_retry_input_without_formal_history(self):
        started, _ = self.begin()
        fresh = CharacterChatService(self.repo, self.transport)
        value = self.repo.load(self.sid)
        attempt = value['requests'][0]['attempts'][0]
        self.assertEqual('interrupted', attempt['status'])
        self.assertNotIn('pending_input', attempt)
        self.assertEqual('合成输入', value['requests'][0]['retry_input']['content'])
        self.assertEqual([], value['turns'])
        self.assertEqual(0, value['revision'])
        await self.service.execute(started['job']['request_id'], lambda *_: None)

    async def test_regenerate_failure_keeps_original_turn_and_ledger(self):
        self.transport.with_ledger = True
        first, _ = await self.send()
        old = self.repo.load(self.sid)
        self.transport.raw = '{bad}'
        second, _ = await self.send(operation='regenerate', target=first['turn_id'])
        new = self.repo.load(self.sid)
        self.assertEqual('failed', second['status'])
        self.assertEqual(old['turns'], new['turns'])
        self.assertEqual(old['ledger'], new['ledger'])
        self.assertEqual('active', new['requests'][0]['result_state'])

    async def test_context_filters_private_entries_before_selection_and_whitelists_profiles(self):
        value = copy.deepcopy(self.session)
        value['participants'][1]['profile_snapshot']['_external_import'] = {'source': 'PRIVATE_CARD_SYNTHETIC'}
        ai = value['participants'][1]['instance_id']
        user = value['participants'][0]['instance_id']
        value['ledger'] = [{'entry_id': str(uuid4()), 'status': 'active', 'kind': 'belief', 'content': 'PRIVATE_LEDGER_SYNTHETIC',
                            'created_turn_id': str(uuid4()), 'visibility': {'audience_instance_ids': [user]}}]
        plan, _, ids, _ = build_context(value, {'content': 'hi', 'mode': 'roleplay', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())})
        self.assertNotIn('PRIVATE_CARD_SYNTHETIC', plan.user_prompt)
        self.assertNotIn('PRIVATE_LEDGER_SYNTHETIC', plan.user_prompt)
        self.assertFalse(ids)
        self.assertIn('roleplay', plan.system_prompt)

    async def test_context_overflow_zero_call_and_safe_failed_attempt(self):
        class SmallTransport(FakeTransport):
            def snapshot(self):
                return {'budget_options': {'context_window': 8192, 'output_reserve': 4096}}
        self.transport = SmallTransport()
        self.service.transport = self.transport
        # Change only our synthetic creation source, no stored profile mutation.
        sid = self.repo.create(create_session(str(uuid4()), {'name': '大资料', 'description': '汉' * 30000},
            {'kind': 'character', 'key': '大资料'}))['session_id']
        self.assert_code('CONTEXT_LIMIT', lambda: self.service.begin(sid, {'client_action_id': str(uuid4()),
            'expected_revision': 0, 'operation': 'send', 'content': 'hello'}))
        self.assertEqual(0, self.transport.calls)
        self.assertEqual('failed', self.repo.load(sid)['requests'][0]['attempts'][0]['status'])

    async def test_two_sessions_do_not_share_messages_or_state(self):
        other = self.repo.create(create_session(str(uuid4()), {'name': '合成角色', 'description': '同角色不同实例'},
            {'kind': 'character', 'key': '合成角色'}))
        await self.send(content='只属于A的文本')
        result = self.service.begin(other['session_id'], {'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'content': '只属于B的文本'})
        await self.service.execute(result['job']['request_id'], lambda *_: None)
        self.assertNotIn('只属于A的文本', self.transport.plans[-1].user_prompt)
        self.assertEqual(1, self.repo.load(other['session_id'])['revision'])

    async def test_old_attempt_finishes_after_retry_cannot_commit(self):
        gate, started = asyncio.Event(), asyncio.Event()
        class LateTransport(FakeTransport):
            async def generate(inner, config, plan, report, delivery, emit):
                inner.calls += 1
                if inner.calls == 1:
                    started.set()
                    try:
                        await gate.wait()
                    except asyncio.CancelledError:
                        # Synthetic uncooperative upstream returns late after cancellation.
                        await gate.wait()
                    return '{"reply":"旧请求迟到","ledger_ops":[]}'
                return '{"reply":"重试新请求","ledger_ops":[]}'
        self.service.transport = LateTransport()
        original, payload = self.begin()
        rid = original['job']['request_id']
        task = asyncio.create_task(self.service.execute(rid, lambda *_: None))
        await started.wait()
        self.service.cancel(self.sid, rid)
        await asyncio.sleep(0)
        retry = self.service.begin(self.sid, {'expected_revision': 0, 'retry_of': rid,
            'retry_token': str(uuid4()), 'delivery': 'non_stream'}, retry_action_id=payload['client_action_id'])
        committed = await self.service.execute(retry['job']['request_id'], lambda *_: None)
        gate.set()
        old = await task
        self.assertEqual('cancelled', old['status'])
        value = self.repo.load(self.sid)
        self.assertEqual('重试新请求', value['turns'][0]['ai_message']['content'])
        self.assertEqual(committed['request_id'], value['turns'][0]['request_id'])
        self.assertEqual(1, value['revision'])

    async def test_pinned_model_budget_and_prompt_are_immutable_inflight(self):
        class MutableTransport(FakeTransport):
            current = {'model': 'original-model', 'budget_options': {'context_window': 32768}}
            observed = None
            def snapshot(inner):
                return copy.deepcopy(inner.current)
            async def generate(inner, config, plan, report, delivery, emit):
                inner.observed = copy.deepcopy(config)
                return await super(MutableTransport, inner).generate(config, plan, report, delivery, emit)
        transport = MutableTransport()
        self.service.transport = transport
        started, _ = self.begin()
        job = self.service.jobs[started['job']['request_id']]
        original_prompt = job['plan'].system_prompt
        transport.current['model'] = 'changed-model'
        transport.current['budget_options']['context_window'] = 8192
        await self.service.execute(started['job']['request_id'], lambda *_: None)
        self.assertEqual('original-model', transport.observed['model'])
        self.assertEqual(32768, transport.observed['budget_options']['context_window'])
        self.assertEqual(original_prompt, transport.plans[-1].system_prompt)

    async def test_four_global_slots_fifth_rejected_without_pending(self):
        jobs = []
        for i in range(5):
            value = self.repo.create(create_session(str(uuid4()), {'name': '并行合成', 'description': '固定资料'},
                {'kind': 'character', 'key': '并行合成'}))
            payload = {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send', 'content': 'hi'}
            if i == 4:
                self.assert_code('CAPACITY_LIMIT', lambda: self.service.begin(value['session_id'], payload))
                self.assertEqual([], self.repo.load(value['session_id'])['requests'])
            else:
                job = self.service.begin(value['session_id'], payload)['job']
                jobs.append(job)
        for job in jobs:
            self.service.cancel(job['session_id'], job['request_id'])
            await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual(0, self.transport.calls)


class CharacterPreviewTests(unittest.TestCase):
    def test_every_split_escaped_chinese_surrogate_pairs(self):
        raw = '{"ledger_ops":[],"reply":"中\\n文\\\"反斜\\\\ emoji \\ud83d\\ude00"}'
        expected = json.loads(raw)['reply']
        for split in range(len(raw) + 1):
            pieces = []
            lexer = ReplyPreview(pieces.append)
            lexer.feed(raw[:split])
            lexer.feed(raw[split:])
            self.assertEqual(expected, ''.join(pieces), split)
        pieces = []
        lexer = ReplyPreview(pieces.append)
        for char in raw:
            lexer.feed(char)
        self.assertEqual(expected, ''.join(pieces))

    def test_nested_reply_never_exposed(self):
        pieces = []
        lexer = ReplyPreview(pieces.append)
        lexer.feed('{"ledger_ops":[{"source":{"reply":"PRIVATE"}}],"reply":"公开"}')
        self.assertEqual('公开', ''.join(pieces))

    def test_strict_final_duplicate_unknown_trailing_surrogate(self):
        for raw in ('{"reply":"a","reply":"b","ledger_ops":[]}', '{"reply":"a","ledger_ops":[],"extra":0}',
                    '{"reply":"a","ledger_ops":[]}tail', '{"reply":"\\ud83d","ledger_ops":[]}'):
            with self.assertRaises(CharacterSessionError):
                parse_result(raw)

    def test_incremental_rejects_unknown_duplicate_unpaired_and_limits(self):
        for raw in ('{"unknown":0}', '{"reply":"a","reply":"b"}', '{"reply":"\\ud83dX"}', '{"reply":3}', '{"reply":"' + 'a' * 8001):
            with self.assertRaises(CharacterSessionError):
                ReplyPreview(lambda _: None).feed(raw)
