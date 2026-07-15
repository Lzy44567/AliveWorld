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
            result = WorldbookWorkshopAgent(ai).respond(workshop, "拓展学校", "expand", commit_changes=True)
            self.assertIn("补充学校制度", result["message"])
            self.assertEqual(result["suggested_actions"], ["继续拓展体育课"])
            self.assertEqual(workshop.draft["entries"][0]["name"], "学校")
            self.assertEqual(len(workshop.messages), 2)

    def test_agent_axiom_is_held_for_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = WorldbookWorkshop("test", Path(temp_dir) / "book.yml", {"name": "世界", "entries": []})
            ai = FakeAI('{"message":"提出新公理","operations":[{"op":"add_entry","entry":{"name":"人口公理","content":"必须提高人口","tags":["绝对规则"]},"creates_axiom":true}],"suggested_actions":[]}')
            result = WorldbookWorkshopAgent(ai).respond(workshop, "建立人口公理", "evolve", commit_changes=True)
            self.assertEqual(result["applied"], [])
            self.assertEqual(len(result["pending"]), 1)

    def test_discussion_mode_persists_reviewable_proposal_without_mutating_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = WorldbookWorkshop("test", Path(temp_dir) / "book.yml", {"name": "世界", "entries": []})
            ai = FakeAI('{"understanding":"先设计学校制度","design_notes":["它应由既有法律推导"],"message":"方案尚未写入","operations":[{"op":"add_entry","entry":{"name":"学校","content":"学校规则","tags":["AI推断","教育"]}}],"suggested_actions":["审阅后写入"]}')
            result = WorldbookWorkshopAgent(ai).respond(workshop, "讨论学校", "expand")
            self.assertEqual(workshop.draft["entries"], [])
            self.assertEqual(result["proposed"][0]["entry"]["name"], "学校")
            self.assertIn("设计依据", result["message"])
            self.assertIn("只讨论与提案", ai.requests[0][1])
            self.assertIn("连续对话", ai.requests[0][0])

    def test_pure_discussion_can_return_without_operations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = WorldbookWorkshop("test", Path(temp_dir) / "book.yml", {"name": "世界", "entries": []})
            ai = FakeAI('{"collaboration_stage":"design","understanding":"正在比较两种规则","design_notes":["尚未达成一致"],"message":"建议先确认代价边界","operations":[],"suggested_actions":["比较方案甲乙"]}')
            result = WorldbookWorkshopAgent(ai).respond(workshop, "哪个方案更好", "evolve")
            self.assertEqual(result["collaboration_stage"], "design")
            self.assertEqual(result["proposed"], [])
            self.assertEqual(workshop.draft["entries"], [])
            self.assertEqual(workshop.suggested_actions, ["比较方案甲乙"])


if __name__ == "__main__":
    unittest.main()
