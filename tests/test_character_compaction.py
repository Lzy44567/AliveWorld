import copy
import json
import unittest
from uuid import uuid4

from core.character_chat import compaction as c
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated
from core.character_chat.group_context import build_group_context
from tests.test_character_multibubble_protocol import result


def conversation(count=22):
    session = convert_legacy_session(create_session(str(uuid4()), {'name': '测试', 'description': '测试'},
                                                  {'kind': 'character', 'key': '测试'}))
    for index in range(count):
        accept_input(session, {'client_action_id': str(uuid4()), 'expected_revision': session['revision'],
                              'content': f'经历{index}', 'ooc_note': '不要进入摘要'})
        attempt = claim_inputs(session, 'instant')
        _, messages, ids, _ = build_group_context(session, attempt['request_id'])
        commit_generated(session, attempt['request_id'], json.dumps(result(f'回应{index}')), messages, ids)
    return session


class CompactionTests(unittest.TestCase):
    def test_default_off_and_explicit_consent(self):
        session = conversation()
        self.assertIsNone(c.prepare(session))
        with self.assertRaises(CharacterSessionError): c.configure(session, True)
        c.configure(session, True, acknowledged=True)
        job = c.prepare(session)
        self.assertEqual(10, len(job['sources']))
        self.assertNotIn('不要进入摘要', json.dumps(job, ensure_ascii=False))
        self.assertEqual(20, len(job['messages']))

    def test_source_edit_invalidates_but_append_does_not(self):
        session = conversation()
        c.configure(session, True, acknowledged=True)
        job = c.prepare(session)
        self.assertTrue(c.commit(session, job, '早期经历'))
        self.assertEqual(1, len(c.references(session)))
        session['revision'] += 1
        self.assertEqual(1, len(c.references(session)))
        session['inputs'][0]['message']['content'] = '已改写'
        self.assertEqual([], c.references(session))
        self.assertEqual(1, c.public_state(session)['invalid_count'])

    def test_disable_and_reenable_reject_late_result(self):
        session = conversation()
        c.configure(session, True, acknowledged=True)
        job = c.prepare(session)
        c.configure(session, False)
        c.configure(session, True, acknowledged=True)
        self.assertFalse(c.commit(session, job, '迟到'))
        self.assertFalse(c.failed(session, job, 'PROVIDER_FAILED'))

    def test_failure_requires_explicit_rebuild_without_advancing(self):
        session = conversation()
        c.configure(session, True, acknowledged=True)
        original = copy.deepcopy(session['inputs'])
        job = c.prepare(session)
        c.failed(session, job, 'PROVIDER_FAILED')
        self.assertIsNone(c.prepare(session))
        self.assertEqual(0, c.state(session)['through_seq'])
        c.rebuild(session)
        self.assertIsNotNone(c.prepare(session, explicit=True))
        self.assertEqual(original, session['inputs'])

    def test_withdrawn_or_incomplete_sources_are_excluded(self):
        session = conversation()
        session['groups'][0]['status'] = 'withdrawn'
        session['groups'][1]['status'] = 'partial_failed'
        self.assertEqual(20, len(c.units(session)))
        c.configure(session, True, acknowledged=True)
        self.assertIsNone(c.prepare(session))

    def test_summary_model_boundary(self):
        self.assertEqual('记忆', c.parse_summary('{"summary":"记忆"}'))
        for raw in ('{}', '[]', '{"summary":1}', '{"summary":""}', json.dumps({'summary': 'x' * 1201})):
            with self.assertRaises(CharacterSessionError): c.parse_summary(raw)

    def test_summary_enters_new_contract_not_evidence_and_schema_roundtrip(self):
        from core.character_chat.group_schema import validate_schema2
        session = conversation()
        c.configure(session, True, acknowledged=True)
        c.commit(session, c.prepare(session), '早期约定一起看海')
        validate_schema2(session)
        accept_input(session, {'client_action_id': str(uuid4()), 'expected_revision': session['revision'], 'content': '还记得吗'})
        attempt = claim_inputs(session, 'instant')
        plan, evidence, _, _ = build_group_context(session, attempt['request_id'])
        data = json.loads(plan.user_prompt)
        self.assertEqual('早期约定一起看海', data['derived_summaries'][0]['summary'])
        self.assertNotIn('早期约定一起看海', json.dumps(evidence, ensure_ascii=False))
        validate_schema2(session)
        c.configure(session, False)
        plan, _, _, _ = build_group_context(session, attempt['request_id'])
        self.assertNotIn('derived_summaries', json.loads(plan.user_prompt))

    def test_long_content_keeps_ten_recent_complete_groups(self):
        session = conversation(12)
        for item in session['inputs']:
            item['message']['content'] = '长消息' * 900
        c.configure(session, True, acknowledged=True)
        job = c.prepare(session)
        self.assertIsNotNone(job)
        self.assertLessEqual(len(job['sources']), 2)


if __name__ == '__main__':
    unittest.main()
