import unittest
from core.character_experiences import with_experiences, for_destination, KEY
from core.character_extraction_agent import extract_character


class CharacterExperienceTests(unittest.TestCase):
    def test_default_no_memories_and_explicit_copy(self):
        card = with_experiences({'name':'林','description':'耐心'}, '记得旧约定', '源世界')
        self.assertEqual({'name':'林','description':'耐心'}, for_destination(card))
        carried = for_destination(card, include_experiences=True)
        self.assertIn('旧约定', carried['description'])
        self.assertIn('不是目标世界历史', carried['description'])
        self.assertNotIn(KEY, carried)
        self.assertEqual('耐心', card['description'])

    def test_model_request_does_not_save_and_preserves_separation(self):
        class Fake:
            def chat_json(self, system, prompt, **kwargs):
                self.prompt = prompt
                return '{"profile":{"description":"耐心"},"experiences":"旧约定","notes":"待审"}', None
        fake = Fake()
        result = extract_character(fake, subject={'id':'npc_1','name':'林'}, profile={}, evidence=[])
        self.assertEqual('耐心', result['profile']['description'])
        self.assertEqual('旧约定', result['experiences'])
        self.assertNotIn('旧约定', result['profile']['description'])
