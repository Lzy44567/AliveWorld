import json
import tempfile
import unittest
from pathlib import Path

from core.prompt_studio import PromptOverrideStore, compose_prompt, require_slice, validate_template


class PromptStudioTests(unittest.TestCase):
    def test_override_is_versioned_persistent_and_restorable(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            baseline = "世界={world_info}；角色={character_info}"
            first = store.save("story.future.core", baseline + "；规则一")
            second = store.save("story.future.core", baseline + "；规则二")
            self.assertEqual((first["version"], second["version"]), (1, 2))
            reloaded = PromptOverrideStore(store.path)
            self.assertEqual(reloaded.get("story.future.core")["content"], baseline + "；规则二")
            self.assertTrue(reloaded.restore("story.future.core"))
            self.assertIsNone(reloaded.get("story.future.core"))

    def test_composition_is_ordered_and_manifest_omits_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            store.save("story.future.core", "核心 {world_info} {character_info}")
            result = compose_prompt(
                "story.future", {"world_info": "世界A", "character_info": "角色A"},
                include={"story.future.core", "story.future.player_agency"},
                runtime_parts=[("story.future.runtime", "运行片段", "runtime")], store=store,
            )
            self.assertTrue(result.text.startswith("核心 世界A 角色A\n\n"))
            self.assertTrue(result.text.endswith("\n\n运行片段"))
            self.assertEqual([item["sliceId"] for item in result.manifest], [
                "story.future.core", "story.future.player_agency", "story.future.runtime",
            ])
            self.assertEqual(result.manifest[0]["source"], "override")
            self.assertNotIn("核心 世界A", json.dumps(result.manifest, ensure_ascii=False))

    def test_validation_rejects_missing_or_unknown_variables(self):
        definition = require_slice("story.future.core")
        with self.assertRaisesRegex(ValueError, "缺少必要变量"):
            validate_template(definition, "只有 {world_info}")
        with self.assertRaisesRegex(ValueError, "未知变量"):
            validate_template(definition, "{world_info} {character_info} {secret}")

    def test_unmigrated_slice_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            with self.assertRaisesRegex(ValueError, "尚不可编辑"):
                store.save("world.capture.runtime", "不应保存")


if __name__ == "__main__":
    unittest.main()
