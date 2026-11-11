import copy
import unittest
from core.character_extraction import prepare_character_card, npc_sources, selected_evidence
from core.character_profiles import CharacterProfileError


class CharacterExtractionTests(unittest.TestCase):
    def test_named_departed_npc_keeps_one_identity(self):
        records = {'npc_a': {'id':'npc_a', 'name':'林', 'aliases':['陌生人'], 'present':False,
                             'last_status':'离场', 'hidden_plan':'不应导出'}}
        self.assertEqual([{'id':'npc_a', 'name':'林', 'aliases':['陌生人'], 'status':'离场'}], npc_sources(records))

    def test_only_selected_public_evidence_is_sent(self):
        turns = [{'turn_id':1, 'player':'问候', 'story':'他点头', 'private':'秘密'},
                 {'turn_id':2, 'player':'离开', 'story':'散场'}]
        self.assertEqual([{'turn_id':1,'player':'问候','story':'他点头'}], selected_evidence(turns,[1]))
        with self.assertRaises(ValueError): selected_evidence(turns,[3])
        with self.assertRaises(ValueError): selected_evidence(turns,[1,1])
    def test_profile_excludes_story_state_and_preserves_source(self):
        source = dict(description='认真', appearance='短发', is_player=True,
                      memories=['私人经历'], ledger=['秘密'], portrait='private/path.png',
                      _external_import={'source': 'private'}, health=2)
        original = copy.deepcopy(source)
        card = prepare_character_card(source, '新角色')
        self.assertEqual('认真', card['description'])
        self.assertFalse(card['is_player'])
        for key in ('memories', 'ledger', 'portrait', '_external_import', 'health'):
            self.assertNotIn(key, card)
        self.assertEqual(original, source)

    def test_structured_fields_preserved_without_aliasing(self):
        fields = dict(version=1, description='底稿', personality='耐心', scenario='',
                      dialogue_examples='你好', first_message='')
        card = prepare_character_card({'role_fields': fields}, '角色')
        self.assertIn('耐心', card['description'])
        card['role_fields']['personality'] = '改变'
        self.assertEqual('耐心', fields['personality'])

    def test_existing_validator_rejects_invalid_model_fields(self):
        with self.assertRaises(CharacterProfileError):
            prepare_character_card({'role_fields': {'version': 99}}, '角色')
