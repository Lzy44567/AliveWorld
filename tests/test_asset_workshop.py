import json
import tempfile
import unittest
from pathlib import Path

import yaml

from core.asset_workshop import AssetWorkshop, AssetWorkshopError
from core.asset_workshop_agent import AssetWorkshopAgent


class FakeEngine:
    def __init__(self, payload):
        self.payload = payload
        self.last_prompt = ""

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.last_prompt = system_prompt + "\n" + user_prompt
        return json.dumps(self.payload, ensure_ascii=False), None


class AssetWorkshopTests(unittest.TestCase):
    def make_workshop(self, asset_type="characters", source=None):
        source = source or {
            "name": "林", "tags": ["角色卡"], "description": "冷静的旅者",
            "starting_scene": "在车站相遇", "is_player": False,
            "portrait": {"task_id": "portrait-1"},
        }
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "asset.yml"
        path.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
        return AssetWorkshop("workshop-1", asset_type, path, source), path

    def test_draft_does_not_change_file_until_publish(self):
        workshop, path = self.make_workshop()
        workshop.apply_operations([{
            "op": "update_fields", "changes": {"description": "冷静但渴望被理解"}
        }])
        self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["description"], "冷静的旅者")
        workshop.publish()
        self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["description"], "冷静但渴望被理解")

    def test_publish_preserves_non_workshop_media_fields(self):
        workshop, path = self.make_workshop()
        workshop.apply_operations([{
            "op": "update_fields", "changes": {"starting_scene": "雨夜相遇"}
        }])
        workshop.publish()
        saved = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["portrait"]["task_id"], "portrait-1")

    def test_publish_rejects_stale_source(self):
        workshop, path = self.make_workshop()
        workshop.apply_operations([{
            "op": "update_fields", "changes": {"description": "工坊修改"}
        }])
        outside = yaml.safe_load(path.read_text(encoding="utf-8"))
        outside["description"] = "编辑器中的新修改"
        path.write_text(yaml.safe_dump(outside, allow_unicode=True), encoding="utf-8")
        with self.assertRaises(AssetWorkshopError):
            workshop.publish()

    def test_ai_cannot_change_player_role_or_runtime_switch(self):
        workshop, _ = self.make_workshop()
        with self.assertRaises(AssetWorkshopError):
            workshop.apply_operations(
                [{"op": "update_fields", "changes": {"is_player": True}}],
                actor="ai",
            )
        entity, _ = self.make_workshop("entities", {
            "name": "议会", "motive": "维持秩序", "status": "稳定", "is_active": True,
        })
        with self.assertRaises(AssetWorkshopError):
            entity.apply_operations(
                [{"op": "update_fields", "changes": {"is_active": False}}],
                actor="ai",
            )

    def test_entity_fields_are_normalized_without_json_exposure_requirement(self):
        workshop, _ = self.make_workshop("entities", {
            "name": "议会", "motive": "维持秩序", "status": "稳定",
        })
        workshop.apply_operations([{
            "op": "update_fields",
            "changes": {
                "mechanisms": "执照制度\n巡查网络",
                "triggers": [{"condition": "秩序崩溃", "result": "进入紧急状态"}],
                "importance": 2,
            },
        }])
        self.assertEqual(workshop.draft["mechanisms"], ["执照制度", "巡查网络"])
        self.assertEqual(workshop.draft["importance"], 1.0)
        self.assertEqual(workshop.draft["triggers"][0]["condition"], "秩序崩溃")

    def test_undo_restores_previous_draft(self):
        workshop, _ = self.make_workshop()
        workshop.apply_operations([{
            "op": "update_fields", "changes": {"description": "第一次修改"}
        }])
        workshop.undo()
        self.assertEqual(workshop.draft["description"], "冷静的旅者")

    def test_persisted_session_can_resume(self):
        workshop, _ = self.make_workshop()
        workshop.apply_operations([{
            "op": "update_fields", "changes": {"description": "持久化草稿"}
        }])
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = workshop.save_session(Path(root.name))
        restored = AssetWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(restored.dirty)
        self.assertEqual(restored.draft["description"], "持久化草稿")

    def test_agent_discussion_proposes_without_mutating(self):
        workshop, _ = self.make_workshop("styles", {
            "name": "克制文风", "tags": ["文风卡"], "content": "短句。",
        })
        engine = FakeEngine({
            "collaboration_stage": "propose",
            "understanding": "希望提高画面感",
            "design_notes": ["保留短句节奏"],
            "message": "先审阅这一版",
            "operations": [{
                "op": "update_fields",
                "changes": {"content": "短句。动作单独成行。"},
                "reason": "增强动作可读性",
            }],
            "suggested_actions": ["比较两种节奏"],
        })
        result = AssetWorkshopAgent(engine).respond(
            workshop, "增加动作画面感", "refine", commit_changes=False
        )
        self.assertEqual(workshop.draft["content"], "短句。")
        self.assertEqual(result["proposed"][0]["changes"]["content"], "短句。动作单独成行。")
        self.assertIn("文风卡工坊", engine.last_prompt)


if __name__ == "__main__":
    unittest.main()
