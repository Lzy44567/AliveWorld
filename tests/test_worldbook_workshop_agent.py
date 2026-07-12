import tempfile
import unittest
from pathlib import Path

from core.worldbook_workshop import WorldbookWorkshop
from core.worldbook_workshop_agent import WorldbookWorkshopAgent


class FakeAI:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.requests.append((system_prompt, user_prompt, kwargs))
        return self.response, None


class WorldbookWorkshopAgentTests(unittest.TestCase):
    def test_agent_applies_low_risk_changes_and_returns_suggestions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = WorldbookWorkshop("test", Path(temp_dir) / "book.yml", {"name": "世界", "entries": []})
            ai = FakeAI('{"message":"补充学校制度","operations":[{"op":"add_entry","entry":{"name":"学校","content":"学校规则","tags":["AI推断"]}}],"suggested_actions":["继续拓展体育课"]}')
            result = WorldbookWorkshopAgent(ai).respond(workshop, "拓展学校", "expand")
            self.assertEqual(result["message"], "补充学校制度")
            self.assertEqual(result["suggested_actions"], ["继续拓展体育课"])
            self.assertEqual(workshop.draft["entries"][0]["name"], "学校")
            self.assertEqual(len(workshop.messages), 2)

    def test_agent_axiom_is_held_for_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = WorldbookWorkshop("test", Path(temp_dir) / "book.yml", {"name": "世界", "entries": []})
            ai = FakeAI('{"message":"提出新公理","operations":[{"op":"add_entry","entry":{"name":"人口公理","content":"必须提高人口","tags":["绝对规则"]},"creates_axiom":true}],"suggested_actions":[]}')
            result = WorldbookWorkshopAgent(ai).respond(workshop, "建立人口公理", "evolve")
            self.assertEqual(result["applied"], [])
            self.assertEqual(len(result["pending"]), 1)


if __name__ == "__main__":
    unittest.main()
