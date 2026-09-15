import json
import tempfile
import unittest
from pathlib import Path

from core.prompt_studio import PromptOverrideStore, compose_prompt, require_slice, validate_template
from core.prompt_variables import VARIABLES, list_variables, resolve_variable


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

    def test_static_core_override_allows_optional_legacy_variables_and_rejects_unknown(self):
        definition = require_slice("story.future.core")
        validate_template(definition, "不嵌入运行资料的静态核心")
        validate_template(definition, "兼容旧世界变量 {world_info}")
        with self.assertRaisesRegex(ValueError, "未知变量"):
            validate_template(definition, "{world_info} {character_info} {secret}")
        self.assertEqual(definition.required_variables, ())

    def test_canonical_variables_and_legacy_aliases_render_identically(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            store.save("story.future.core", "{{context.world}}；{{context.player_character}}")
            canonical = compose_prompt(
                "story.future",
                {"context.world": "世界A", "context.player_character": "角色A"},
                include={"story.future.core"}, store=store,
            )
            legacy = compose_prompt(
                "story.future", {"world_info": "世界A", "character_info": "角色A"},
                include={"story.future.core"}, store=store,
            )
            self.assertEqual(canonical.text, legacy.text)
            self.assertEqual(canonical.text, "世界A；角色A")

    def test_canonical_value_wins_and_whitespace_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            store.save(
                "story.future.core",
                "世界={{   context.world   }}；角色={{context.player_character}}",
            )
            result = compose_prompt(
                "story.future",
                {
                    "world_info": "旧调用值",
                    "context.world": "规范值",
                    "context.player_character": "角色",
                },
                include={"story.future.core"},
                store=store,
            )
            self.assertEqual(result.text, "世界=规范值；角色=角色")

    def test_variable_registry_has_unique_safe_metadata(self):
        ids = [item.id for item in VARIABLES]
        aliases = [alias for item in VARIABLES for alias in item.legacy_aliases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertTrue(all(item.description and item.allowed_tasks for item in VARIABLES))
        self.assertFalse(any("key" in item.id.lower() or "password" in item.id.lower() for item in VARIABLES))
        self.assertEqual(resolve_variable("world_info").id, "context.world")
        self.assertEqual(list_variables()[0]["syntax"], "{{context.world}}")

    def test_manifest_exposes_layers_and_stable_prefix_hashes(self):
        first = compose_prompt(
            "story.future", {"world_info": "世界A", "character_info": "角色A"},
            include={"story.future.core"},
            runtime_parts=[("story.future.runtime", "行动一", "runtime")],
        )
        second = compose_prompt(
            "story.future", {"world_info": "世界A", "character_info": "角色A"},
            include={"story.future.core"},
            runtime_parts=[("story.future.runtime", "行动二", "runtime")],
        )
        self.assertEqual(first.manifest[0]["prefixHash"], second.manifest[0]["prefixHash"])
        self.assertNotEqual(first.manifest[-1]["prefixHash"], second.manifest[-1]["prefixHash"])
        self.assertEqual(first.manifest[0]["layer"], "engine")
        self.assertEqual(first.manifest[-1]["cacheClass"], "turn")

    def test_unmigrated_slice_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            with self.assertRaisesRegex(ValueError, "尚不可编辑"):
                store.save("world.capture.runtime", "不应保存")

    def test_state_guidance_is_editable_but_state_contract_is_protected(self):
        self.assertTrue(require_slice("story.state.guidance").editable)
        self.assertFalse(require_slice("story.state.contract").editable)
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            with self.assertRaisesRegex(ValueError, "尚不可编辑"):
                store.save("story.state.contract", "{}")


if __name__ == "__main__":
    unittest.main()
