import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.group_lifecycle import (accept_input, claim_inputs, commit_generated,
    deliver, fail_generation, recover_groups, mark_read, gap_seconds, batch_action, retry_group)
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_records import formal_messages, pending_inputs, unread_messages, conversation_projection
from core.character_chat.group_schema import validate_schema2
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.repository import CharacterSessionRepository
from tests.test_character_multibubble_protocol import result


class GroupLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name), validator=validate_schema2, supported_schemas=(2,))
        self.initial = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                                             {'kind': 'character', 'key': '合成'}))
        self.sid = self.initial['session_id']; self.repo.create(self.initial)
        self.clock = datetime.now(timezone.utc)

    def load(self):
        return self.repo.load(self.sid)

    def mutate(self, fn):
        def op(session):
            before = copy.deepcopy(session)
            returned = fn(session)
            return returned, session != before
        return self.repo.transaction(self.sid, op)

    def send(self, content='输入', note=None, claim=False, mode='stream', action_id=None):
        before = self.load()
        payload = {'client_action_id': action_id or str(uuid4()), 'expected_revision': before['revision'], 'content': content}
        if note:
            payload['ooc_note'] = note
        def op(session):
            action, changed = accept_input(session, payload)
            attempt = claim_inputs(session, mode) if claim and changed else None
            return {'action': copy.deepcopy(action), 'attempt': attempt}, changed
        return self.repo.transaction(self.sid, op), payload

    def complete(self, attempt, value=None):
        return self.mutate(lambda s: commit_generated(s, attempt['request_id'], json.dumps(value or result('一', '第二句', '第三句')), [], set(), self.clock))

    def test_stream_and_instant_single_atomic_batch_no_candidate_sources(self):
        for mode in ('stream', 'instant'):
            sent, _ = self.send(claim=True, mode=mode)
            before = self.load()
            self.assertEqual(1 if mode == 'stream' else 5, len(formal_messages(before)))
            group = self.complete(sent['attempt'])
            self.assertEqual('complete', group['status'])
            self.assertEqual(3, group['delivered_count'])
            self.assertEqual(3 if mode == 'stream' else 6, len(unread_messages(self.load())))
            self.assertEqual([], pending_inputs(self.load()))
            self.assertEqual(1 if mode == 'stream' else 2, sum(a['attempts'] != [] for a in self.load()['requests']))

    def test_gaps_first_immediate_tail_not_formal_and_idempotent_due(self):
        sent, _ = self.send(claim=True, mode='gaps')
        group = self.complete(sent['attempt'])
        self.assertEqual('delivering', group['status'])
        self.assertEqual(1, group['delivered_count'])
        self.assertEqual(2, len(formal_messages(self.load())))
        self.assertEqual(1, len(unread_messages(self.load())))
        def send_next(s, clock, ordinal):
            g = next(g for g in s['groups'] if g['group_id'] == group['group_id'])
            return deliver(s, g, clock, ordinal)
        before = self.load()
        self.assertFalse(self.mutate(lambda s: send_next(s, self.clock, 1)))
        self.assertEqual(before, self.load())
        late = self.clock + timedelta(seconds=10)
        self.assertTrue(self.mutate(lambda s: send_next(s, late, 1)))
        second = self.load()
        self.assertFalse(self.mutate(lambda s: send_next(s, late + timedelta(seconds=10), 1)))
        self.assertEqual(second, self.load())
        self.assertTrue(self.mutate(lambda s: send_next(s, late + timedelta(seconds=10), 2)))
        after = self.load()
        self.assertEqual('complete', after['groups'][0]['status'])
        self.assertEqual(4, len(formal_messages(after)))

    def test_batch_end_ledger_only_then_source_matches_specific_bubble(self):
        sent, _ = self.send(claim=True, mode='gaps')
        value = result('先说一句', '约好了')
        ids = [p['instance_id'] for p in self.initial['participants']]
        value['ledger_ops'] = [{'op': 'add', 'kind': 'experience', 'content': '本轮作出约定',
            'source': {'type': 'dialogue_event', 'message_ids': ['b1'], 'evidence': [{'message_id': 'b1', 'quote': '约好了'}]},
            'visibility': {'audience_instance_ids': ids}}]
        value['memory_annotations'] = [{'op_index': 0, 'reason': 'commitment'}]
        group = self.complete(sent['attempt'], value)
        before = self.load()
        self.assertEqual([], before['ledger'])
        self.assertEqual(1, len(before['groups'][0]['ledger_plan']))
        self.assertNotIn(sent['attempt']['reserved_ai_ids'][1], formal_messages(before))
        self.mutate(lambda s: deliver(s, s['groups'][0], self.clock + timedelta(seconds=10), 1))
        after = self.load()
        self.assertEqual(sent['attempt']['reserved_ai_ids'][1], after['ledger'][0]['source']['message_ids'][0])
        self.assertEqual('complete', after['groups'][0]['status'])
        self.assertEqual([], after['groups'][0]['ledger_plan'])

    def test_new_inputs_while_generating_or_delivering_do_not_cancel_batch(self):
        sent, _ = self.send('A', claim=True, mode='gaps')
        self.send('X', '独立场外X')
        # Ordinary input increments revision but not context_epoch.
        self.complete(sent['attempt'])
        self.send('Y', '独立场外Y')
        self.assertEqual(['X', 'Y'], [i['message']['content'] for i in pending_inputs(self.load())])
        self.mutate(lambda s: deliver(s, s['groups'][0], self.clock + timedelta(seconds=10), 1))
        self.mutate(lambda s: deliver(s, s['groups'][0], self.clock + timedelta(seconds=20), 2))
        attempt = self.mutate(lambda s: claim_inputs(s, 'instant'))
        entries = {i['input_id']: i for i in self.load()['inputs']}
        self.assertEqual(['X', 'Y'], [entries[mid]['message']['content'] for mid in attempt['input_ids']])
        self.assertEqual(2, len(attempt['input_ids']))
        self.assertEqual('独立场外X', entries[attempt['input_ids'][0]]['ooc_note'])
        self.assertEqual('独立场外Y', entries[attempt['input_ids'][1]]['ooc_note'])
        self.complete(attempt, result('回应X与Y'))
        self.assertEqual([], pending_inputs(self.load()))
        self.assertEqual(2, sum(len(a['attempts']) for a in self.load()['requests']))
        self.assertIsNone(self.mutate(lambda s: claim_inputs(s)))

    def test_idempotent_send_and_cas_conflict_no_duplicate_input(self):
        aid = str(uuid4())
        sent, payload = self.send('原输入', action_id=aid)
        old = self.load()
        duplicate = self.repo.transaction(self.sid, lambda s: accept_input(s, payload))
        self.assertEqual(old, self.load())
        self.assertEqual(sent['action'], duplicate)
        mismatch = dict(payload, content='改变输入')
        for bad in (mismatch, dict(payload, client_action_id=str(uuid4()), expected_revision=0)):
            with self.assertRaises(CharacterSessionError):
                self.repo.transaction(self.sid, lambda s: accept_input(s, bad))
        self.assertEqual(1, len(self.load()['inputs']))

    def test_queue_limit_preserves_formal_inputs_and_rejects_extra(self):
        self.send('已认领', claim=True)
        for i in range(8):
            self.send(f'排队{i}')
        before = self.load()
        with self.assertRaises(CharacterSessionError):
            self.send('第九条')
        self.assertEqual(before, self.load())

    def test_failure_bad_source_atomic_then_explicit_continue_same_inputs(self):
        sent, _ = self.send('A', claim=True)
        self.send('X')
        value = result('未保存预览')
        value['ledger_ops'] = [{'op': 'add', 'kind': 'knowledge', 'content': '假来源',
            'source': {'type': 'player_statement', 'message_ids': ['b0'], 'evidence': [{'message_id': 'b0', 'quote': '未保存'}]},
            'visibility': {'audience_instance_ids': [p['instance_id'] for p in self.initial['participants']]}}]
        before = self.load()
        with self.assertRaises(CharacterSessionError):
            self.complete(sent['attempt'], value)
        self.assertEqual(before, self.load())
        self.mutate(lambda s: fail_generation(s, sent['attempt']['request_id']))
        self.assertEqual(['A', 'X'], [i['message']['content'] for i in pending_inputs(self.load())])
        # State transitions never themselves start a provider. Explicit continuation
        # claims the existing input IDs instead of duplicating the player's lines.
        self.assertIsNone(self.mutate(lambda s: claim_inputs(s, 'instant')))
        attempt = self.mutate(lambda s: claim_inputs(s, 'instant', explicit=True))
        self.assertEqual([i['input_id'] for i in self.load()['inputs']], attempt['input_ids'])
        self.complete(attempt, result('一起回应'))
        self.assertEqual(2, len(self.load()['inputs']))

    def test_epoch_change_late_reply_rejected_but_formal_player_input_retained(self):
        sent, _ = self.send('A', claim=True)
        def changed(s):
            s['context_epoch'] += 1; s['revision'] += 1
        self.mutate(changed)
        before = self.load()
        with self.assertRaises(CharacterSessionError):
            self.complete(sent['attempt'])
        self.assertEqual(before, self.load())

    def test_storage_failure_no_half_messages_ledger_or_sequences(self):
        sent, _ = self.send('A', claim=True)
        before = self.load()
        with patch.object(self.repo, '_write', side_effect=CharacterSessionError('PERSISTENCE_FAILED')):
            with self.assertRaises(CharacterSessionError):
                self.complete(sent['attempt'])
        self.assertEqual(before, self.load())

    def test_restart_pending_interrupted_or_remaining_candidate_rescheduled(self):
        sent, _ = self.send('A', claim=True)
        self.assertTrue(self.mutate(lambda s: recover_groups(s, self.clock)))
        self.assertEqual('interrupted', self.load()['groups'][0]['status'])
        attempt = self.mutate(lambda s: claim_inputs(s, 'gaps', explicit=True))
        self.complete(attempt)
        before = self.load()
        self.assertTrue(self.mutate(lambda s: recover_groups(s, self.clock + timedelta(hours=2))))
        after = self.load()
        self.assertEqual(before['groups'][-1]['bubbles'], after['groups'][-1]['bubbles'])
        self.assertEqual(1, after['groups'][-1]['delivered_count'])
        self.assertGreater(datetime.fromisoformat(after['groups'][-1]['next_due_at']), self.clock + timedelta(hours=2))

    def test_read_cursor_never_reads_preview_or_future_and_old_ack_not_rollback(self):
        sent, _ = self.send('A', claim=True, mode='gaps')
        self.complete(sent['attempt'])
        first_seq = unread_messages(self.load())[0]['seq']
        with self.assertRaises(CharacterSessionError):
            self.mutate(lambda s: mark_read(s, first_seq + 1))
        self.assertTrue(self.mutate(lambda s: mark_read(s, first_seq)))
        self.mutate(lambda s: deliver(s, s['groups'][0], self.clock + timedelta(seconds=10), 1))
        self.assertFalse(self.mutate(lambda s: mark_read(s, first_seq - 1)))
        self.assertEqual(1, len(unread_messages(self.load())))

    def test_gap_codepoint_calculation_has_short_min_and_long_cap(self):
        self.assertEqual(.1, gap_seconds(' '))
        self.assertEqual(.2, gap_seconds('🙂中'))
        self.assertEqual(3, gap_seconds('字' * 500))

    def test_failed_full_input_and_full_queue_continue_in_bounded_prefixes(self):
        sent, _ = self.send('A' * 4000, claim=True)
        self.send('X' * 4000)
        self.mutate(lambda s: fail_generation(s, sent['attempt']['request_id']))
        self.assertIsNone(self.mutate(lambda s: claim_inputs(s)))
        first = self.mutate(lambda s: claim_inputs(s, 'instant', explicit=True))
        self.assertEqual(1, len(first['input_ids']))
        self.complete(first, result('回应原输入'))
        second = self.mutate(lambda s: claim_inputs(s, 'instant'))
        self.assertEqual(1, len(second['input_ids']))
        self.assertNotEqual(first['input_ids'], second['input_ids'])
        self.complete(second, result('回应排队输入'))
        self.assertEqual([], pending_inputs(self.load()))
        self.assertEqual(2, len(self.load()['inputs']))

    def test_cancel_requires_explicit_continue_and_does_not_consume_turn_capacity(self):
        from core.character_chat.group_records import capacity_groups
        sent, _ = self.send('A', claim=True)
        self.mutate(lambda s: fail_generation(s, sent['attempt']['request_id'], 'cancelled', 'USER_CANCELLED'))
        before = self.load()
        self.assertIsNone(self.mutate(lambda s: claim_inputs(s)))
        self.assertEqual(before, self.load())
        self.assertEqual([], capacity_groups(before))
        attempt = self.mutate(lambda s: claim_inputs(s, explicit=True))
        self.assertEqual(sent['attempt']['input_ids'], attempt['input_ids'])
        self.assertEqual(1, len(capacity_groups(self.load())))

    def test_tampered_candidate_plan_and_reverse_identity_fail_before_restore(self):
        sent, _ = self.send('A', claim=True, mode='gaps')
        value = result('第一条', '第二条')
        value['ledger_ops'] = [{'op': 'add', 'kind': 'experience', 'content': '记录',
            'source': {'type': 'dialogue_event', 'message_ids': ['b1'], 'evidence': [{'message_id': 'b1', 'quote': '第二条'}]},
            'visibility': {'audience_instance_ids': [p['instance_id'] for p in self.initial['participants']]}}]
        self.complete(sent['attempt'], value)
        original = self.load()
        bad = []
        altered = copy.deepcopy(original); altered['groups'][0]['ledger_plan'][0]['entry']['source']['message_ids'] = [str(uuid4())]; bad.append(altered)
        altered = copy.deepcopy(original); altered['groups'][0]['ledger_plan'][0]['entry']['source']['type'] = 'author'; bad.append(altered)
        altered = copy.deepcopy(original); altered['groups'][0]['ledger_plan'][0]['entry']['source']['evidence'] = []; bad.append(altered)
        altered = copy.deepcopy(original); altered['groups'][0]['ledger_plan'][0]['entry']['hidden'] = 'not-a-field'; bad.append(altered)
        altered = copy.deepcopy(original); altered['requests'][0]['attempts'][0]['group_id'] = str(uuid4()); bad.append(altered)
        altered = copy.deepcopy(original); altered['requests'][0]['attempts'][0]['reserved_ai_ids'][5] = original['inputs'][0]['input_id']; bad.append(altered)
        for altered in bad:
            with self.subTest(altered=str(altered)[:80]), self.assertRaises(CharacterSessionError):
                validate_schema2(altered)
        self.assertEqual(original, self.load())

    def batch(self, operation, action_id=None):
        session = self.load()
        target = next(g for g in reversed(session['groups']) if g['status'] == 'complete')
        payload = {'client_action_id': action_id or str(uuid4()), 'expected_revision': session['revision'],
                   'operation': operation, 'target_group_id': target['group_id']}
        return self.repo.transaction(self.sid, lambda s: batch_action(s, payload, 'instant'))

    def test_whole_batch_undo_preserves_archive_ids_and_never_reuses_sequences(self):
        sent, _ = self.send('台词', '关联场外', claim=True, mode='instant')
        self.complete(sent['attempt'])
        original = self.load()
        next_seq = original['next_seq']
        self.batch('undo')
        withdrawn = self.load()
        self.assertEqual([], conversation_projection(withdrawn))
        self.assertEqual(original['groups'][0]['bubbles'], withdrawn['groups'][0]['bubbles'])
        self.assertEqual('withdrawn', withdrawn['inputs'][0]['status'])
        self.assertEqual('关联场外', withdrawn['inputs'][0]['ooc_note'])
        self.assertEqual(next_seq, withdrawn['next_seq'])
        sent, _ = self.send('新台词', claim=True)
        self.assertEqual(next_seq, self.load()['inputs'][-1]['message']['seq'])
        self.complete(sent['attempt'], result('新的回应'))
        self.assertEqual(2, len(conversation_projection(self.load())))

    def test_regeneration_failure_keeps_batch_then_retry_reuses_exact_input_ids(self):
        sent, _ = self.send('原台词', '原说明', claim=True, mode='instant')
        self.complete(sent['attempt'])
        original = self.load()
        attempt = self.batch('regenerate')
        self.assertEqual(list(formal_messages(original)), list(formal_messages(self.load())))
        bad = result('新候选'); bad['extra'] = True
        with self.assertRaises(CharacterSessionError):
            self.complete(attempt, bad)
        self.mutate(lambda s: fail_generation(s, attempt['request_id']))
        owner = next(a for a in self.load()['requests'] if any(t['request_id'] == attempt['request_id'] for t in a['attempts']))
        token = str(uuid4())
        retried = self.repo.transaction(self.sid, lambda s: retry_group(s, owner['action_id'], attempt['request_id'], token, 'instant'))
        self.assertEqual(attempt['input_ids'], retried['input_ids'])
        self.complete(retried, result('重新回应', '第二条重新回应'))
        after = self.load()
        self.assertEqual(1, len(after['inputs']))
        self.assertEqual('原说明', after['inputs'][0]['ooc_note'])
        self.assertEqual('replaced', after['groups'][0]['status'])
        self.assertEqual(3, len(conversation_projection(after)))
        self.assertNotIn(original['groups'][0]['bubbles'][0]['message']['message_id'], formal_messages(after))

    def test_regeneration_interjection_blocks_replacement_preserves_original_and_new_input(self):
        sent, _ = self.send('原台词', claim=True, mode='instant')
        self.complete(sent['attempt'])
        original = self.load()
        attempt = self.batch('regenerate')
        self.send('我正在回应旧剧情')
        before = self.load()
        with self.assertRaises(CharacterSessionError):
            self.complete(attempt, result('不同剧情'))
        self.assertEqual(before, self.load())
        self.assertEqual(original['groups'][0]['bubbles'], self.load()['groups'][0]['bubbles'])
        self.mutate(lambda s: fail_generation(s, attempt['request_id']))
        self.assertEqual(['我正在回应旧剧情'], [i['message']['content'] for i in pending_inputs(self.load())])

    def test_undo_rejects_unanswered_followup_and_delivery_in_progress(self):
        sent, _ = self.send('原台词', claim=True, mode='instant')
        self.complete(sent['attempt'])
        self.send('后续台词')
        before = self.load()
        with self.assertRaises(CharacterSessionError):
            self.batch('undo')
        self.assertEqual(before, self.load())
        queued = self.mutate(lambda s: claim_inputs(s, 'gaps'))
        self.complete(queued)
        with self.assertRaises(CharacterSessionError):
            self.batch('undo')

    def test_retry_idempotency_then_resolved_input_cannot_be_paid_replied_twice(self):
        sent, _ = self.send('台词', claim=True)
        self.mutate(lambda s: fail_generation(s, sent['attempt']['request_id']))
        token = str(uuid4())
        aid = sent['action']['action_id']
        original = sent['attempt']['request_id']
        retry = self.repo.transaction(self.sid, lambda s: retry_group(s, aid, original, token, 'instant'))
        before = self.load()
        duplicate = self.repo.transaction(self.sid, lambda s: retry_group(s, aid, original, token, 'instant'))
        self.assertEqual(retry, duplicate)
        self.assertEqual(before, self.load())
        self.complete(retry, result('回应一次'))
        with self.assertRaises(CharacterSessionError):
            self.repo.transaction(self.sid, lambda s: retry_group(s, aid, original, str(uuid4()), 'instant'))
        self.assertEqual(1, len(self.load()['inputs']))
        self.assertEqual(2, len(self.load()['requests'][0]['attempts']))

    def test_interjection_between_bubbles_protects_whole_batch_from_undo_and_regenerate(self):
        sent, _ = self.send('U', claim=True, mode='gaps')
        self.complete(sent['attempt'], result('A', 'B'))
        self.send('X是在回应A')
        self.mutate(lambda s: deliver(s, s['groups'][0], self.clock + timedelta(seconds=10), 1))
        before = self.load()
        self.assertEqual(['U', 'A', 'X是在回应A', 'B'], [r['message']['content'] for r in conversation_projection(before)])
        for operation in ('undo', 'regenerate'):
            with self.assertRaises(CharacterSessionError):
                self.batch(operation)
            self.assertEqual(before, self.load())

    def test_failed_cancelled_retry_chain_then_undo_keeps_valid_attempt_archives(self):
        sent, _ = self.send('台词', claim=True)
        aid = sent['action']['action_id']
        self.mutate(lambda s: fail_generation(s, sent['attempt']['request_id']))
        first = self.repo.transaction(self.sid, lambda s: retry_group(s, aid, sent['attempt']['request_id'], str(uuid4()), 'instant'))
        self.mutate(lambda s: fail_generation(s, first['request_id'], 'cancelled', 'USER_CANCELLED'))
        second = self.repo.transaction(self.sid, lambda s: retry_group(s, aid, first['request_id'], str(uuid4()), 'instant'))
        self.complete(second, result('正式成功'))
        self.batch('undo')
        after = self.load()
        self.assertEqual(['failed', 'cancelled', 'withdrawn'], [g['status'] for g in after['groups']])
        self.assertEqual([], conversation_projection(after))
        self.assertEqual('withdrawn', after['inputs'][0]['status'])
        self.assertEqual(3, len(after['requests'][0]['attempts']))

    def test_failed_regeneration_does_not_block_undo_of_retained_original_batch(self):
        sent, _ = self.send('台词', claim=True, mode='instant')
        self.complete(sent['attempt'])
        attempt = self.batch('regenerate')
        self.mutate(lambda s: fail_generation(s, attempt['request_id']))
        self.batch('undo')
        after = self.load()
        self.assertEqual(['withdrawn', 'failed'], [g['status'] for g in after['groups']])
        self.assertEqual([], conversation_projection(after))

    def test_full_turn_capacity_allows_regeneration_retry_but_not_new_send(self):
        sent, _ = self.send('台词', claim=True, mode='instant')
        self.complete(sent['attempt'])
        with patch('core.character_chat.group_lifecycle.MAX_TURNS', 1):
            attempt = self.batch('regenerate')
            self.mutate(lambda s: fail_generation(s, attempt['request_id']))
            owner = next(a for a in self.load()['requests'] if a['operation'] == 'regenerate')
            retry = self.repo.transaction(self.sid, lambda s: retry_group(s, owner['action_id'], attempt['request_id'], str(uuid4()), 'instant'))
            self.complete(retry, result('容量满时可替换'))
            with self.assertRaises(CharacterSessionError):
                self.send('不能新增')


if __name__ == '__main__':
    unittest.main()
