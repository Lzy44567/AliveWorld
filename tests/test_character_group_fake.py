import unittest
from core.character_chat.message_groups import validate_messages
from tests.fakes.character_group_reply import response


class GroupFakeTests(unittest.TestCase):
    def test_separate_v3_fixture_keeps_independent_inputs_and_bounded_array(self):
        result = response({'context_contract_id': 'character.context.c4.v1',
                           'current_user_messages': [{'content': '甲'}, {'content': '乙'}]})
        validate_messages(result['messages'])
        self.assertEqual(list(result), ['messages', 'ledger_ops', 'memory_annotations'])
        self.assertIn('甲 / 乙', result['messages'][0]['text'])
        self.assertEqual(result['ledger_ops'], [])

    def test_malformed_fixture_is_explicit_and_old_context_is_not_reinterpreted(self):
        with self.assertRaises(ValueError):
            response({'context_contract_id': 'character.context.m3.v1'})
        result = response({'context_contract_id': 'character.context.c4.v1',
                           'current_user_messages': [{'content': '【C4坏JSON】'}]})
        self.assertTrue(result.endswith(' trailing'))
