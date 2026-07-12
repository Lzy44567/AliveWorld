import tempfile
import unittest
from pathlib import Path

import yaml

from core.worldbook_workshop import WorkshopError, WorldbookWorkshop


class WorldbookWorkshopTests(unittest.TestCase):
    def make_workshop(self, directory):
        source = {
            "name": "测试世界",
            "entries": [
                {"id": "entry_law", "name": "基础法律", "content": "旧法律", "tags": ["玩家设定"]},
                {"id": "entry_axiom", "name": "世界公理", "content": "不可违背", "tags": ["绝对规则"]},
            ],
        }
        return WorldbookWorkshop("workshop_test", Path(directory) / "world.yml", source)

    def test_low_risk_operations_modify_draft_and_can_undo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = self.make_workshop(temp_dir)
            result = workshop.apply_operations([{"op": "add_entry", "entry": {"name": "学校", "content": "学校制度"}}])
            self.assertEqual(len(result["applied"]), 1)
            self.assertEqual(len(workshop.draft["entries"]), 3)
            workshop.undo()
            self.assertEqual(len(workshop.draft["entries"]), 2)

    def test_absolute_rule_and_delete_require_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = self.make_workshop(temp_dir)
            result = workshop.apply_operations([
                {"op": "update_entry", "entry_id": "entry_axiom", "changes": {"content": "新公理"}},
                {"op": "request_delete", "entry_id": "entry_law", "reason": "不再需要"},
            ])
            self.assertEqual(result["applied"], [])
            self.assertEqual(len(result["pending"]), 2)
            workshop.approve(result["pending"][1]["operation_id"])
            deleted = next(item for item in workshop.draft["entries"] if item["id"] == "entry_law")
            self.assertFalse(deleted["is_active"])
            self.assertIn("待删除", deleted["tags"])

    def test_axiom_flag_requires_confirmation_even_without_absolute_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = self.make_workshop(temp_dir)
            result = workshop.apply_operations([{
                "op": "add_entry", "entry": {"name": "新公理", "content": "改变世界基调"}, "creates_axiom": True,
            }])
            self.assertEqual(result["applied"], [])
            self.assertEqual(len(result["pending"]), 1)

    def test_unknown_operation_and_entry_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = self.make_workshop(temp_dir)
            with self.assertRaises(WorkshopError):
                workshop.apply_operations([{"op": "delete_file", "path": "other.yml"}])
            with self.assertRaises(WorkshopError):
                workshop.apply_operations([{"op": "update_entry", "entry_id": "missing", "changes": {"content": "x"}}])

    def test_publish_writes_normalized_draft_and_session_can_reload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = self.make_workshop(temp_dir)
            workshop.apply_operations([{"op": "add_entry", "entry": {"name": "服装", "content": "服装规则"}}])
            output = workshop.publish()
            saved = yaml.safe_load(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["name"], "测试世界")
            session_path = workshop.save_session(Path(temp_dir) / "sessions")
            import json
            loaded = WorldbookWorkshop.from_dict(json.loads(session_path.read_text(encoding="utf-8")))
            self.assertEqual(len(loaded.draft["entries"]), 3)


if __name__ == "__main__":
    unittest.main()
