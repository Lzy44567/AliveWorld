import copy
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated
from core.character_chat.legacy_context import build_legacy_retry_context
from core.character_chat.protocol import V1, V2
from core.character_chat.context_contract import LEGACY, M3, C3
from tests.test_character_multibubble_protocol import result


class LegacyContextTests(unittest.TestCase):
    def setUp(self):
        self.session = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                                              {'kind': 'character', 'key': '合成'}))
        self.pending = {'content': '旧台词', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
        self.action = {'operation': 'send', 'legacy_retry_snapshot': self.pending}
        self.attempt = {'legacy_attempt': True, 'reply_contract_id': V1, 'context_contract_id': M3}

    def group(self, user='过去', *replies):
        accept_input(self.session, {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'], 'content': user})
        attempt = claim_inputs(self.session)
        return commit_generated(self.session, attempt['request_id'], json.dumps(result(*(replies or ('甲', '乙')))), [], set())

    def build(self):
        plan, evidence, ids, report = build_legacy_retry_context(self.session, self.action, self.attempt)
        return plan, json.loads(plan.user_prompt), evidence, ids, report

    def test_six_contract_context_combinations_keep_original_single_input_ids(self):
        for protocol in (V1, V2):
            for context in (LEGACY, M3, C3):
                with self.subTest(protocol=protocol, context=context):
                    self.attempt.update(reply_contract_id=protocol, context_contract_id=context)
                    self.pending.pop('ooc_note', None)
                    if context == C3: self.pending['ooc_note'] = '旧场外'
                    plan, data, evidence, _, _ = self.build()
                    self.assertEqual(protocol, plan.contract_id); self.assertEqual(context, plan.context_contract_id)
                    self.assertEqual(self.pending['user_message_id'], data['current_user_message']['message_id'])
                    self.assertEqual(self.pending['ai_message_id'], data['current_ai_message_id'])
                    self.assertEqual(context != LEGACY, 'recalled_sources' in data)
                    self.assertEqual(context == C3, 'current_ooc_note' in data)
                    self.assertNotIn('current_user_messages', data)
                    self.assertEqual([], evidence)

    def test_missing_optional_protocols_preserve_legacy_defaults(self):
        self.attempt = {'legacy_attempt': True}
        plan, data, _, _, _ = self.build()
        self.assertEqual(V1, plan.contract_id); self.assertEqual(LEGACY, plan.context_contract_id)
        self.assertNotIn('context_contract_id', data)

    def test_real_multibubble_history_not_concatenated_or_duplicated(self):
        self.group('过去输入', '真实甲', '真实乙', '真实丙')
        before = copy.deepcopy(self.session)
        _, data, evidence, _, _ = self.build()
        self.assertEqual(['过去输入', '真实甲', '真实乙', '真实丙'], [m['content'] for m in data['history']])
        self.assertEqual(data['history'], evidence)
        self.assertEqual(before, self.session); self.assertNotIn('turns', self.session)

    def test_unanswered_input_is_not_legacy_history(self):
        self.group()
        accept_input(self.session, {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'], 'content': '新队列不能混入旧请求'})
        _, data, _, _, _ = self.build()
        self.assertNotIn('新队列不能混入旧请求', json.dumps(data, ensure_ascii=False))

    def test_regeneration_excludes_original_user_and_ai_without_mutating_source(self):
        target = self.group('旧分支输入', '旧分支甲', '旧分支乙')
        self.action.update(operation='regenerate', target_group_id=target['group_id'])
        before = copy.deepcopy(self.session)
        _, data, evidence, _, _ = self.build()
        self.assertEqual([], data['history']); self.assertEqual([], evidence)
        self.assertEqual('旧台词', data['current_user_message']['content'])
        self.assertEqual(before, self.session)

    def test_protocol_or_ooc_identity_conflicts_are_not_reinterpreted(self):
        self.pending['reply_contract_id'] = V2
        with self.assertRaises(CharacterSessionError): self.build()
        self.pending.pop('reply_contract_id'); self.pending['ooc_note'] = '说明'
        with self.assertRaises(CharacterSessionError): self.build()
        self.pending.pop('ooc_note'); self.attempt['context_contract_id'] = C3
        with self.assertRaises(CharacterSessionError): self.build()

    def test_budget_trims_whole_groups_and_keeps_original_input(self):
        for n in range(3): self.group(f'输入{n}', f'甲{n}', f'乙{n}')
        with patch('core.character_chat.context.budget_report', side_effect=[{'fits': False}, {'fits': True}]):
            _, data, _, _, report = self.build()
        self.assertEqual(['输入1', '甲1', '乙1', '输入2', '甲2', '乙2'], [m['content'] for m in data['history']])
        self.assertEqual('旧台词', data['current_user_message']['content'])
        self.assertEqual([{'turn_id': self.session['groups'][0]['group_id']}], report['omitted'])


if __name__ == '__main__': unittest.main()
