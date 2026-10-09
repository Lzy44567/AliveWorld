import copy
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.character_chat.group_creation import create_group_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated, batch_action, require_group_retry
from core.character_chat.group_records import formal_messages, unread_messages
from core.character_chat.group_schema import validate_schema2
from core.character_chat.group_settings import metadata
from core.character_chat.group_views import public_session, action_view
from core.character_chat.models import CharacterSessionError
from core.character_chat import proactive_contact as contact
from tests.test_character_multibubble_protocol import result


class ProactiveContactTests(unittest.TestCase):
    def setUp(self):
        self.session = create_group_session(str(uuid4()), {'name': '合成', 'description': '测试'},
                                            {'kind': 'character', 'key': '合成'})
        self.clock = datetime.now(timezone.utc)

    def configure(self, **patch):
        return contact.configure(self.session, self.session['revision'], patch)

    def send(self):
        return accept_input(self.session, {'client_action_id': str(uuid4()),
                            'expected_revision': self.session['revision'], 'content': '你好'})

    def arm(self):
        self.configure(enabled=True)
        self.send()
        attempt = claim_inputs(self.session, 'instant')
        import json
        commit_generated(self.session, attempt['request_id'], json.dumps(result('正常答复')), [], set())

    def plan(self, contacts=None):
        self.arm()
        pid = str(uuid4())
        planned = contact.mark_planning(self.session, pid, self.clock.strftime('%Y-%m-%d'),
            self.clock + timedelta(hours=1), 2, self.clock,
            allowed_message_ids=list(formal_messages(self.session)))
        self.assertIsNotNone(planned)
        self.assertTrue(contact.save_plan(self.session, pid, contacts if contacts is not None else [
            {'delay_seconds': 0, 'reply': result('主动一句', '主动第二句')}], self.clock))
        validate_schema2(self.session)
        return pid

    def test_old_schema2_defaults_do_not_create_extension(self):
        before = copy.deepcopy(self.session)
        self.assertFalse(contact.settings(self.session)['enabled'])
        contact.on_user_input(self.session)
        contact.invalidate(self.session)
        self.assertEqual(before, self.session)
        self.assertNotIn('proactive_contact', self.session['extensions'])

    def test_configuration_waits_for_new_input_and_validates(self):
        self.configure(enabled=True)
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])
        self.assertIsNone(contact.mark_planning(self.session, str(uuid4()), '2026-10-09',
                                              self.clock + timedelta(hours=1), 2))
        for patch in ({'enabled': 1}, {'idle_seconds': 0}, {'max_contacts': 6}, {'unknown': True}):
            with self.assertRaises(CharacterSessionError):
                contact.configure(self.session, self.session['revision'], patch)
        self.send()
        self.assertEqual('armed', contact.settings(self.session)['cycle_state'])
        self.assertEqual(1, contact.settings(self.session)['interaction_epoch'])

    def test_formal_instant_no_fake_input_private_plan_and_replay(self):
        pid = self.plan()
        before_inputs = copy.deepcopy(self.session['inputs'])
        public = public_session(self.session)
        self.assertNotIn('主动一句', str(public))
        group = contact.commit_proactive_contact(self.session, pid, 0)
        self.assertEqual([], group['input_ids'])
        self.assertEqual('proactive', group['origin'])
        self.assertEqual('complete', group['status'])
        self.assertEqual('instant', group['display_mode'])
        self.assertEqual(2, group['delivered_count'])
        self.assertEqual(before_inputs, self.session['inputs'])
        self.assertEqual(3, len(unread_messages(self.session)))
        owner = self.session['requests'][-1]
        self.assertEqual('active', owner['result_state'])
        self.assertEqual('proactive', owner['operation'])
        self.assertNotIn('input_id', owner)
        self.assertNotIn('memory_notice', group)
        self.assertFalse(action_view(self.session, owner)['retryable'])
        before = copy.deepcopy(self.session)
        self.assertEqual(group, contact.commit_proactive_contact(self.session, pid, 0))
        self.assertEqual(before, self.session)
        self.assertEqual('exhausted', contact.settings(self.session)['cycle_state'])
        self.assertIsNone(contact.state(self.session)['plan'])
        validate_schema2(self.session)

    def test_proactive_ledger_undo_reverses_without_player_input(self):
        value = result('我记得这件事')
        audience = [p['instance_id'] for p in self.session['participants']]
        value['ledger_ops'] = [{'op': 'add', 'kind': 'experience', 'content': '主动说起此事',
            'source': {'type': 'dialogue_event', 'message_ids': ['b0'],
                       'evidence': [{'message_id': 'b0', 'quote': '这件事'}]},
            'visibility': {'audience_instance_ids': audience}}]
        value['memory_annotations'] = [{'op_index': 0, 'reason': 'commitment'}]
        pid = self.plan([{'delay_seconds': 0, 'reply': value}])
        group = contact.commit_proactive_contact(self.session, pid, 0)
        self.assertEqual(1, len(self.session['ledger']))
        self.assertNotIn('memory_notice', group)
        self.assertEqual(group['bubbles'][0]['message']['message_id'],
                         self.session['ledger'][0]['source']['message_ids'][0])
        batch_action(self.session, {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'],
            'operation': 'undo', 'target_group_id': group['group_id']})
        self.assertEqual([], self.session['ledger'])
        self.assertEqual('withdrawn', self.session['groups'][-1]['status'])
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])
        validate_schema2(self.session)

    def test_regenerate_and_retry_explicitly_rejected(self):
        pid = self.plan()
        group = contact.commit_proactive_contact(self.session, pid, 0)
        before = copy.deepcopy(self.session)
        with self.assertRaises(CharacterSessionError) as raised:
            batch_action(self.session, {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'],
                'operation': 'regenerate', 'target_group_id': group['group_id']})
        self.assertEqual('REPLY_CONTRACT_UNSUPPORTED', raised.exception.code)
        self.assertEqual(before, self.session)
        owner = self.session['requests'][-1]
        with self.assertRaises(CharacterSessionError):
            require_group_retry(self.session, owner, group['request_id'])

    def test_player_input_cancels_plan_and_blocks_old_undo(self):
        pid = self.plan()
        group = contact.commit_proactive_contact(self.session, pid, 0)
        self.send()
        with self.assertRaises(CharacterSessionError):
            batch_action(self.session, {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'],
                'operation': 'undo', 'target_group_id': group['group_id']})
        self.assertEqual(2, contact.settings(self.session)['interaction_epoch'])

    def test_new_input_and_authorization_cancel_inflight_plans(self):
        pid = self.plan()
        self.send()
        self.assertIsNone(contact.commit_proactive_contact(self.session, pid, 0))
        self.assertFalse(contact.save_plan(self.session, pid, []))
        self.assertIsNone(contact.state(self.session)['plan'])
        self.configure(paused=True)
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])
        self.configure(paused=False)
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])

    def test_empty_plan_consumes_cycle_and_restart_preserves_authorization(self):
        self.plan([])
        self.assertEqual('exhausted', contact.settings(self.session)['cycle_state'])
        contact.invalidate(self.session)
        self.assertTrue(contact.settings(self.session)['enabled'])
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])
        self.assertIsNone(contact.mark_planning(self.session, str(uuid4()), '2026-10-09',
                                              self.clock + timedelta(hours=1), 2))

    def test_context_changes_cancel_but_title_and_read_do_not(self):
        pid = self.plan()
        metadata(self.session, self.session['revision'], title='新标题')
        self.assertIsNotNone(contact.plan_current(self.session, pid))
        metadata(self.session, self.session['revision'], presentation_mode='roleplay')
        self.assertIsNone(contact.plan_current(self.session, pid))
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])

    def test_total_plan_text_and_existing_extension_budget(self):
        self.arm()
        pid = str(uuid4())
        contact.mark_planning(self.session, pid, '2026-10-09', self.clock + timedelta(hours=1), 2)
        with self.assertRaises(CharacterSessionError):
            contact.save_plan(self.session, pid, [{'delay_seconds': 0, 'reply': result('一' * 5000)},
                                                  {'delay_seconds': 1, 'reply': result('二' * 5000)}])
        self.session['extensions']['other'] = 'x' * 30000
        with self.assertRaises(CharacterSessionError) as raised:
            contact.save_plan(self.session, pid, [{'delay_seconds': 0, 'reply': result('一' * 1000)}])
        self.assertEqual('SESSION_LIMIT', raised.exception.code)

    def test_multiple_contacts_delivered_candidate_body_is_cleared(self):
        pid = self.plan([{'delay_seconds': 0, 'reply': result('第一组')},
                         {'delay_seconds': 0, 'reply': result('第二组')}])
        first = contact.commit_proactive_contact(self.session, pid, 0)
        self.assertEqual('', contact.state(self.session)['plan']['contacts'][0]['reply'])
        self.assertEqual(1, contact.state(self.session)['plan']['next_index'])
        validate_schema2(self.session)
        self.assertEqual(first, contact.commit_proactive_contact(self.session, pid, 0))
        second = contact.commit_proactive_contact(self.session, pid, 1)
        self.assertNotEqual(first['group_id'], second['group_id'])
        self.assertEqual('exhausted', contact.settings(self.session)['cycle_state'])
        validate_schema2(self.session)

    def test_due_and_expiry_are_checked_before_commit(self):
        pid = self.plan([{'delay_seconds': 20, 'reply': result('到期再见')}])
        before = copy.deepcopy(self.session)
        self.assertIsNone(contact.commit_proactive_contact(self.session, pid, 0, self.clock))
        self.assertEqual(before, self.session)
        self.assertIsNotNone(contact.commit_proactive_contact(self.session, pid, 0, self.clock + timedelta(seconds=20)))
        validate_schema2(self.session)
        self.session = create_group_session(str(uuid4()), {'name': '合成', 'description': '测试'},
                                            {'kind': 'character', 'key': '合成'})
        pid = self.plan()
        self.assertIsNone(contact.commit_proactive_contact(self.session, pid, 0, self.clock + timedelta(hours=2)))
        self.assertEqual('idle', contact.settings(self.session)['cycle_state'])

    def test_saved_commit_reloads_and_replays_without_duplicates(self):
        import tempfile
        from pathlib import Path
        from core.character_chat.repository import CharacterSessionRepository
        pid = self.plan()
        with tempfile.TemporaryDirectory() as path:
            repo = CharacterSessionRepository(Path(path), validator=validate_schema2, supported_schemas=(2,))
            sid = self.session['session_id']
            repo._write(self.session)  # Seed a validated persisted plan fixture.
            def commit(session):
                before = copy.deepcopy(session)
                group = contact.commit_proactive_contact(session, pid, 0)
                return group, session != before
            first = repo.transaction(sid, commit)
            reloaded = repo.load(sid)
            second = repo.transaction(sid, commit)
            self.assertEqual(first, second)
            self.assertEqual(reloaded, repo.load(sid))
            self.assertEqual(1, sum(g.get('origin') == 'proactive' for g in reloaded['groups']))


if __name__ == '__main__':
    unittest.main()
