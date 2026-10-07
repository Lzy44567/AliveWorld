import copy
import json
import unittest
from uuid import uuid4
from unittest.mock import patch

from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated, batch_action, fail_generation
from core.character_chat.group_context import build_group_context
from core.character_chat.group_schema import validate_schema2
from core.character_chat.prompts import CORE_V3, CONTRACT_V3
from core.character_chat.protocol import V3
from core.character_chat.context_contract import C4
from tests.test_character_multibubble_protocol import result
from tests.test_character_world_context import session as world_session, entry


class GroupContextTests(unittest.TestCase):
    def setUp(self):
        self.session = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                                             {'kind': 'character', 'key': '合成'}))

    def send(self, text, note=None):
        payload = {'client_action_id': str(uuid4()), 'expected_revision': self.session['revision'], 'content': text}
        if note:
            payload['ooc_note'] = note
        return accept_input(self.session, payload)[0]

    def build(self, attempt, **kwargs):
        plan, messages, ids, report = build_group_context(self.session, attempt['request_id'], **kwargs)
        return plan, json.loads(plan.user_prompt), messages, ids, report

    def complete(self, attempt, value=None):
        _, _, messages, ids, _ = self.build(attempt)
        return commit_generated(self.session, attempt['request_id'], json.dumps(value or result('甲', '乙')), messages, ids)

    def test_distinct_inputs_ooc_identity_and_no_queued_future(self):
        self.send('第一条', '场外甲'); self.send('第二条', '场外乙')
        attempt = claim_inputs(self.session)
        self.send('不属于当前请求', '不可泄漏')
        before = copy.deepcopy(self.session)
        plan, data, evidence, _, report = self.build(attempt)
        self.assertEqual(V3, plan.contract_id); self.assertEqual(C4, plan.context_contract_id)
        self.assertEqual(['第一条', '第二条'], [m['content'] for m in data['current_user_messages']])
        self.assertEqual(attempt['input_ids'], [n['message_id'] for n in data['current_ooc_notes']])
        self.assertEqual(['场外甲', '场外乙'], [n['content'] for n in data['current_ooc_notes']])
        self.assertEqual([], data['history']); self.assertNotIn('不可泄漏', plan.user_prompt)
        self.assertEqual(attempt['input_ids'], [m['message_id'] for m in evidence])
        self.assertNotIn('current_user_message', data); self.assertNotIn('current_ai_message_id', data)
        self.assertTrue(report['fits']); self.assertEqual(before, self.session)

    def test_whole_completed_batch_reused_without_historical_ooc(self):
        self.send('过去台词', '旧场外不能重放'); old = claim_inputs(self.session); self.complete(old)
        self.send('本次'); attempt = claim_inputs(self.session)
        _, data, evidence, _, _ = self.build(attempt)
        self.assertEqual(['过去台词', '甲', '乙'], [m['content'] for m in data['history']])
        self.assertEqual(4, len(evidence)); self.assertEqual([], data['current_ooc_notes'])
        self.assertNotIn('旧场外不能重放', json.dumps(data, ensure_ascii=False))
        self.assertEqual(sorted(m['seq'] for m in data['history']), [m['seq'] for m in data['history']])

    def test_regeneration_excludes_original_output_and_restores_input(self):
        self.send('原输入', '原场外'); first = claim_inputs(self.session); group = self.complete(first)
        attempt, _ = batch_action(self.session, {'client_action_id': str(uuid4()),
            'expected_revision': self.session['revision'], 'target_group_id': group['group_id'], 'operation': 'regenerate'})
        _, data, evidence, _, _ = self.build(attempt)
        self.assertEqual([], data['history']); self.assertEqual(['原输入'], [m['content'] for m in evidence])
        self.assertEqual('原场外', data['current_ooc_notes'][0]['content'])

    def test_source_ledger_and_annotation_can_cite_second_input_and_bubble(self):
        self.send('闲聊'); self.send('我喜欢蓝色', '这是场外')
        attempt = claim_inputs(self.session)
        user = next(p['instance_id'] for p in self.session['participants'] if p['controller'] == 'user')
        ai = next(p['instance_id'] for p in self.session['participants'] if p['controller'] == 'ai')
        mid = attempt['input_ids'][1]
        value = result('知道啦')
        value['ledger_ops'] = [{'op': 'add', 'kind': 'knowledge', 'content': '玩家表示喜欢蓝色', 'about_instance_id': user,
            'source': {'type': 'player_statement', 'message_ids': [mid], 'evidence': [{'message_id': mid, 'quote': '喜欢蓝色'}]},
            'visibility': {'audience_instance_ids': [user, ai]}}]
        value['memory_annotations'] = [{'op_index': 0, 'reason': 'explicit_preference'}]
        self.complete(attempt, value)
        self.send('蓝色'); new = claim_inputs(self.session)
        _, data, _, ids, report = self.build(new)
        self.assertEqual(mid, data['ledger'][0]['source']['message_ids'][0])
        self.assertEqual({data['ledger'][0]['entry_id']}, ids)
        self.assertEqual('sent', report['memory_context']['entries'][0]['state'])
        validate_schema2(self.session)

    def test_budget_never_truncates_current_inputs_or_notes(self):
        self.send('完整台词', '完整场外'); attempt = claim_inputs(self.session)
        before = copy.deepcopy(self.session)
        with self.assertRaises(CharacterSessionError) as caught:
            self.build(attempt, budget_options={'context_window': 100, 'output_reserve': 50})
        self.assertEqual('CONTEXT_LIMIT', caught.exception.code); self.assertEqual(before, self.session)

    def test_invalid_epoch_or_protocol_rejected_before_request(self):
        self.send('输入'); attempt = claim_inputs(self.session)
        self.session['context_epoch'] += 1
        with self.assertRaises(CharacterSessionError): self.build(attempt)
        self.session['context_epoch'] -= 1
        self.session['requests'][0]['attempts'][0]['reply_contract_id'] = 'character.reply.v2'
        with self.assertRaises(CharacterSessionError): self.build(attempt)

    def test_static_prompt_has_new_identity_and_no_old_reply_shape(self):
        self.assertNotIn('character.reply.v2', CORE_V3)
        self.assertIn('character.reply.v3', CORE_V3)
        self.assertNotIn('"reply":', CONTRACT_V3)
        self.assertIn('memory_annotations必填', CONTRACT_V3)

    def test_world_keywords_ignore_ooc_future_and_replaced_bubbles(self):
        self.session = convert_legacy_session(world_session([entry(k) for k in ['OLD', 'NOW', 'OOC', 'FUTURE']]))
        self.send('旧输入'); first = claim_inputs(self.session); group = self.complete(first, result('OLD'))
        attempt, _ = batch_action(self.session, {'client_action_id': str(uuid4()),
            'expected_revision': self.session['revision'], 'target_group_id': group['group_id'], 'operation': 'regenerate'})
        self.complete(attempt, result('替换无关键词'))
        self.send('NOW', 'OOC'); attempt = claim_inputs(self.session); self.send('FUTURE')
        _, data, _, _, _ = self.build(attempt, preferences=[{'content': '偏好OOC'}])
        self.assertEqual(['NOW'], [e['id'] for e in data['world_related_entries']])
        self.assertEqual([{'content': '偏好OOC'}], data['user_preferences'])
        self.assertEqual(['规则'], data['world_rules']['axioms'])

    def test_old_source_recall_preserves_exact_seq_identity_outside_twenty_groups(self):
        self.send('我喜欢蓝色'); first = claim_inputs(self.session)
        user, ai = [next(p['instance_id'] for p in self.session['participants'] if p['controller'] == kind) for kind in ('user', 'ai')]
        mid = first['input_ids'][0]
        value = result('记住了')
        value['ledger_ops'] = [{'op': 'add', 'kind': 'knowledge', 'content': '玩家表示喜欢蓝色', 'about_instance_id': user,
            'source': {'type': 'player_statement', 'message_ids': [mid], 'evidence': [{'message_id': mid, 'quote': '喜欢蓝色'}]},
            'visibility': {'audience_instance_ids': [user, ai]}}]
        value['memory_annotations'] = [{'op_index': 0, 'reason': 'explicit_preference'}]
        self.complete(first, value)
        original = copy.deepcopy(self.session['inputs'][0]['message'])
        for _ in range(20):
            self.send('别的话题'); self.complete(claim_inputs(self.session), result('普通回应'))
        self.send('蓝色'); attempt = claim_inputs(self.session)
        _, data, evidence, _, _ = self.build(attempt)
        self.assertNotIn(mid, [m['message_id'] for m in data['history']])
        self.assertEqual([original], data['recalled_sources'])
        self.assertEqual(original, next(m for m in evidence if m['message_id'] == mid))
        with patch('core.character_chat.group_context.budget_report', side_effect=[{'fits': False}, {'fits': True}]):
            _, cut, evidence, _, report = self.build(attempt)
        self.assertEqual([], cut['recalled_sources'])
        self.assertNotIn(mid, [m['message_id'] for m in evidence])
        self.assertEqual([{'field': 'recalled_sources'}], report['omitted'])
        self.complete(attempt, result('回应')); validate_schema2(self.session)

    def test_bounded_claim_excludes_unclaimed_inputs_even_before_cutoff(self):
        for n in range(8): self.send(f'旧{n}' + '字' * 398)
        first = claim_inputs(self.session)
        for n in range(8): self.send(f'后{n}' + '字' * 398)
        fail_generation(self.session, first['request_id'], 'failed', 'MODEL_ERROR')
        attempt = claim_inputs(self.session, explicit=True)
        _, data, evidence, _, _ = self.build(attempt)
        self.assertEqual(first['input_ids'], attempt['input_ids'])
        self.assertEqual(8, len(data['current_user_messages']))
        self.assertTrue(all(m['content'].startswith('旧') for m in evidence))
        self.assertNotIn('后0', json.dumps(data, ensure_ascii=False))

    def test_legacy_storage_does_not_enter_new_context(self):
        old = create_session(str(uuid4()), {'name': '旧', 'description': '固定'}, {'kind': 'character', 'key': '旧'})
        with self.assertRaises(CharacterSessionError) as caught:
            build_group_context(old, str(uuid4()))
        self.assertEqual('REPLY_CONTRACT_UNSUPPORTED', caught.exception.code)

    def test_budget_removes_preferences_then_whole_groups_not_individual_bubbles(self):
        for n in range(3):
            self.send(f'输入{n}'); self.complete(claim_inputs(self.session), result(f'甲{n}', f'乙{n}'))
        self.send('当前'); attempt = claim_inputs(self.session)
        calls = 0
        def budget(*args, **kwargs):
            nonlocal calls
            calls += 1
            return {'fits': calls >= 3}
        with patch('core.character_chat.group_context.budget_report', side_effect=budget):
            _, data, _, _, report = self.build(attempt, preferences=[{'content': '可裁剪偏好'}])
        self.assertEqual(['输入1', '甲1', '乙1', '输入2', '甲2', '乙2'], [m['content'] for m in data['history']])
        self.assertNotIn('user_preferences', data)
        self.assertEqual(['当前'], [m['content'] for m in data['current_user_messages']])
        self.assertEqual('user_preferences', report['omitted'][0]['field'])
        self.assertIn('group_id', report['omitted'][1])


if __name__ == '__main__':
    unittest.main()
