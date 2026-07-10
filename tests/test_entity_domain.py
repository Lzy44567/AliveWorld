import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.entities import Entity, active_entities
from core.entity_repository import EntityRepository
from core.shadow_ledger import ShadowLedger
from core.undercurrent import UndercurrentEngine


class FakeAIEngine:
    def __init__(self, response):
        self.response = response
        self.system_prompt = ""

    def chat_json(self, system_prompt, _user_prompt, temp=0.8):
        self.system_prompt = system_prompt
        return self.response, None


class EntityDomainTests(unittest.TestCase):
    def test_legacy_goal_is_read_as_motive_and_extra_is_preserved(self):
        entity = Entity.from_dict({"name": "皇城", "goal": "追捕玩家", "description": "旧资产", "is_active": False})

        self.assertEqual(entity.motive, "追捕玩家")
        self.assertFalse(entity.is_active)
        self.assertEqual(entity.to_dict()["description"], "旧资产")
        self.assertNotIn("goal", entity.to_dict())
        self.assertEqual(active_entities([entity]), [])

    def test_repository_round_trip_and_prunes_deleted_entity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EntityRepository(temp_dir)
            entity = Entity.from_dict({"name": "世界推演", "motive": "维持演化", "plans": ["观察"]})
            repository.synchronize([entity])

            stored = yaml.safe_load((Path(temp_dir) / "entities" / "世界推演.yml").read_text(encoding="utf-8"))
            self.assertEqual(stored["motive"], "维持演化")
            self.assertEqual(repository.load()[0].plans, ["观察"])

            repository.synchronize([])
            self.assertEqual(repository.load(), [])

    def test_ledger_accepts_legacy_strings_and_limits_context(self):
        ledger = ShadowLedger(["[Tick 1] 旧暗流"])
        ledger.record(2, "action", "皇城", "派遣密探", ["客栈"])

        self.assertEqual(len(ledger.export()), 2)
        self.assertIn("皇城：派遣密探", ledger.context())
        self.assertLessEqual(len(ledger.context(character_limit=10)), 10)

    def test_world_simulation_template_is_a_structured_active_entity(self):
        template_path = Path(__file__).resolve().parents[1] / "templates" / "entities" / "世界推演.yml"
        template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        entity = Entity.from_dict(template)

        self.assertEqual(entity.name, "世界推演")
        self.assertTrue(entity.is_active)
        self.assertEqual(entity.importance, 0.6)
        self.assertIn("世界推演", entity.tags)
        self.assertTrue(entity.mechanisms)

    def test_overseer_excludes_inactive_entity_and_records_active_action(self):
        response = '{"undercurrent_events":[{"entity":"皇城","action":"派遣密探","status":"戒备","new_plans":["搜查客栈"],"new_mechanisms":["守卫盘查"],"new_triggers":[{"condition":"玩家进城","result":"盘查"}],"relationship_updates":{"玩家":"敌对"},"clues":["密探出没"]},{"entity":"封存势力","action":"不应执行"}],"new_entities":[],"update_entities":[{"name":"皇城","status":"追查中"}],"delete_entities":[]}'
        ai_engine = FakeAIEngine(response)
        engine = UndercurrentEngine(ai_engine)
        engine.entities = [
            Entity(
                name="皇城",
                motive="追捕玩家",
                mechanisms=["既有盘查机制"],
                triggers=[{"condition": "玩家进城", "result": "守卫盘查"}],
                relationships={"玩家": "敌对"},
            ),
            Entity(name="封存势力", motive="不应出现", is_active=False),
        ]

        with patch("core.undercurrent.load_system_prompts", return_value={"overseer_prompt": "实体：{entities_info}\n剧情：{world_context}"}):
            engine.tick("玩家进入城镇")

        self.assertIn("皇城", ai_engine.system_prompt)
        self.assertNotIn("封存势力", ai_engine.system_prompt)
        self.assertIn("既有盘查机制", ai_engine.system_prompt)
        self.assertIn("玩家进城→守卫盘查", ai_engine.system_prompt)
        self.assertEqual(engine.entities[0].recent_actions, ["派遣密探"])
        self.assertEqual(engine.entities[0].status, "追查中")
        self.assertEqual(engine.entities[0].plans, ["搜查客栈"])
        self.assertEqual(engine.entities[0].mechanisms, ["既有盘查机制", "守卫盘查"])
        self.assertEqual(engine.entities[0].relationships, {"玩家": "敌对"})
        self.assertIn("皇城：派遣密探", engine.get_ledger_context())
        self.assertIn("计划：搜查客栈", engine.get_ledger_context())
        self.assertIn("机制：守卫盘查", engine.get_ledger_context())
        self.assertNotIn("封存势力：不应执行", engine.get_ledger_context())
        self.assertEqual(engine.export_state()["shadow_ledger"][-1]["details"]["new_plans"], ["搜查客栈"])


if __name__ == "__main__":
    unittest.main()
