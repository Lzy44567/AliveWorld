import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated, fail_generation, batch_action
from core.character_chat.group_schema import validate_schema2
from core.character_chat.group_views import public_session, session_summary, group_page, action_view
from core.character_chat import group_settings
from tests.test_character_multibubble_protocol import result


class GroupViewsTests(unittest.TestCase):
    def setUp(self):
        self.value = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定',
                                               '_external_import': {'secret': 'PRIVATE_EXTENSION'}},
                                               {'kind': 'character', 'key': '合成'}, opening_text='开场白'))

    def send(self, content='输入', note=''):
        payload = {'client_action_id': str(uuid4()), 'expected_revision': self.value['revision'], 'content': content}
        if note: payload['ooc_note'] = note
        return accept_input(self.value, payload)[0]

    def complete(self, texts=('甲', '乙'), mode='instant', memory=False):
        attempt = claim_inputs(self.value, mode)
        body = result(*texts)
        if memory:
            body['ledger_ops'] = [{'op': 'add', 'kind': 'experience', 'content': '约定',
                                  'source': {'type': 'dialogue_event', 'message_ids': ['b0'],
                                             'evidence': [{'message_id': 'b0', 'quote': texts[0]}]},
                                  'visibility': {'audience_instance_ids': [p['instance_id'] for p in self.value['participants']]}}]
            body['memory_annotations'] = [{'op_index': 0, 'reason': 'commitment'}]
        return commit_generated(self.value, attempt['request_id'], json.dumps(body), [], set())

    def test_detail_has_real_messages_groups_and_no_internal_or_import_data(self):
        self.send(note='场外'); self.complete()
        view = public_session(self.value)
        self.assertEqual(2, view['schema_version']); self.assertNotIn('turns', view)
        self.assertEqual(['输入', '甲', '乙'], [r['message']['content'] for r in view['messages']])
        self.assertEqual('场外', view['messages'][0]['ooc_note'])
        self.assertEqual('开场白', view['opening']['content'])
        raw = json.dumps(view)
        for key in ('PRIVATE_EXTENSION', 'ledger_inverse', 'ledger_plan', 'context_epoch', 'reserved_ai_ids', 'profile_semantics'):
            self.assertNotIn(key, raw)

    def test_queued_claimed_and_resolved_child_action_points_to_owner(self):
        first = self.send('X'); child = self.send('Y')
        self.assertEqual('queued', action_view(self.value, child)['status'])
        attempt = claim_inputs(self.value)
        state = action_view(self.value, child)
        self.assertEqual('pending', state['status']); self.assertEqual(attempt['request_id'], state['request_id'])
        with self.assertRaises(CharacterSessionError): action_view(self.value, child, attempt['request_id'])
        group = commit_generated(self.value, attempt['request_id'], json.dumps(result('回答XY')), [], set())
        state = action_view(self.value, child)
        self.assertEqual('committed', state['status']); self.assertEqual(group['group_id'], state['resolved_by_group_id'])
        self.assertEqual(first['attempts'][-1]['request_id'], state['request_id'])

    def test_candidate_tail_not_in_detail_summary_or_unread(self):
        self.send(); group = self.complete(('首条', 'PRIVATE_TAIL'), mode='gaps')
        view = public_session(self.value); summary = session_summary(self.value)
        self.assertNotIn('PRIVATE_TAIL', json.dumps(view)); self.assertNotIn('PRIVATE_TAIL', json.dumps(summary))
        self.assertEqual(1, view['unread_count']); self.assertEqual(1, view['groups'][0]['delivered_count'])
        self.assertEqual('首条', summary['last_message_preview'])
        self.assertEqual('delivering', action_view(self.value, self.value['requests'][0])['group_status'])

    def test_summary_separates_latest_user_from_latest_ai(self):
        self.send(); group = self.complete()
        self.send('新消息')
        summary = session_summary(self.value)
        self.assertEqual('user_input', summary['last_message_kind']); self.assertEqual('新消息', summary['last_message_preview'])
        self.assertEqual(group['bubbles'][-1]['message']['message_id'], summary['latest_ai_message_id'])
        self.assertEqual(2, summary['unread_count']); self.assertEqual(1, summary['queued_count'])

    def test_whole_group_pagination_and_invalidated_cursor(self):
        groups = []
        for n in range(3):
            self.send(f'输入{n}'); groups.append(self.complete((f'甲{n}', f'乙{n}')))
        page = group_page(self.value, limit=2)
        self.assertEqual([groups[1]['group_id'], groups[2]['group_id']], [g['group_id'] for g in page['groups']])
        self.assertEqual(6, len(page['messages']))
        old = group_page(self.value, before=page['next_cursor'], limit=2)
        self.assertEqual(3, len(old['messages'])); self.assertIsNone(old['next_cursor'])
        batch_action(self.value, {'client_action_id': str(uuid4()), 'expected_revision': self.value['revision'],
                                 'operation': 'undo', 'target_group_id': groups[-1]['group_id']})
        with self.assertRaises(CharacterSessionError) as caught: group_page(self.value, before=groups[-1]['group_id'])
        self.assertEqual('REVISION_CONFLICT', caught.exception.code)

    def test_cancelled_retry_eligible_until_inputs_resolved_by_another_group(self):
        action = self.send(); attempt = claim_inputs(self.value)
        fail_generation(self.value, attempt['request_id'], 'cancelled', 'USER_CANCELLED')
        self.assertTrue(action_view(self.value, action)['retryable'])
        self.send('继续'); next_attempt = claim_inputs(self.value, explicit=True)
        commit_generated(self.value, next_attempt['request_id'], json.dumps(result('继续回复')), [], set())
        self.assertFalse(action_view(self.value, action)['retryable'])

    def test_metadata_title_busy_allowed_context_change_atomic_rejected(self):
        self.send(); attempt = claim_inputs(self.value)
        epoch = self.value['context_epoch']
        group_settings.metadata(self.value, self.value['revision'], title='改名')
        self.assertEqual(epoch, self.value['context_epoch'])
        before = copy.deepcopy(self.value)
        with self.assertRaises(CharacterSessionError): group_settings.metadata(self.value, self.value['revision'], title='不能部分改', presentation_mode='roleplay')
        self.assertEqual(before, self.value)
        fail_generation(self.value, attempt['request_id'])
        with self.assertRaises(CharacterSessionError): group_settings.metadata(self.value, self.value['revision'], presentation_mode='roleplay')

    def test_memory_sources_and_busy_notice_ack_leave_epoch_unchanged(self):
        action = self.send(); group = self.complete(('约好了',), memory=True)
        eid = self.value['ledger'][0]['entry_id']
        source = group_settings.memory_sources(self.value, eid)
        self.assertEqual(group['bubbles'][0]['message']['message_id'], source['messages'][0]['message_id'])
        self.assertTrue(group_settings.mark_memory(self.value, self.value['revision'], eid, True))
        self.send('下一批'); claim_inputs(self.value)
        epoch = self.value['context_epoch']
        self.assertTrue(group_settings.update_memory(self.value, self.value['revision'], 'acknowledge', action['action_id']))
        self.assertEqual(epoch, self.value['context_epoch'])
        with self.assertRaises(CharacterSessionError): group_settings.mark_memory(self.value, self.value['revision'], eid, False)
        validate_schema2(self.value)

    def test_undo_uses_own_control_attempt_not_target_generation(self):
        self.send(); group = self.complete()
        action, _ = batch_action(self.value, {'client_action_id': str(uuid4()), 'expected_revision': self.value['revision'],
                                  'operation': 'undo', 'target_group_id': group['group_id']})
        state = action_view(self.value, action)
        self.assertEqual(action['attempts'][-1]['request_id'], state['request_id'])
        self.assertEqual(self.value['revision'], state['committed_revision'])
        self.assertNotEqual(group['request_id'], state['request_id'])

    def test_explicit_failed_request_does_not_report_later_owner_group(self):
        action = self.send(); attempt = claim_inputs(self.value)
        fail_generation(self.value, attempt['request_id'])
        self.send('继续'); new_attempt = claim_inputs(self.value, explicit=True)
        commit_generated(self.value, new_attempt['request_id'], json.dumps(result('新回复')), [], set())
        latest = action_view(self.value, action)
        old = action_view(self.value, action, attempt['request_id'])
        self.assertEqual('committed', latest['status']); self.assertEqual(new_attempt['group_id'], latest['group_id'])
        self.assertEqual('failed', old['status']); self.assertEqual(attempt['group_id'], old['group_id'])
        self.assertFalse(old['retryable']); self.assertNotIn('memory_notice', old)
