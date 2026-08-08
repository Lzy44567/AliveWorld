import json
import tempfile
import unittest
from pathlib import Path

from core.image_generation.models import ImageTask
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.image_generation.workflows import WorkflowDefinition, WorkflowError, WorkflowRepository
from core.image_generation.workflow_profiles import WorkflowProfileRepository, compose_prompt


class FakeComfyUIProvider(ComfyUIProvider):
    def __init__(self, responses, **kwargs):
        super().__init__(**kwargs)
        self.responses = dict(responses)
        self.requests = []

    def _request_json(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        response = self.responses.get((method, path), {})
        return response() if callable(response) else response

    def _request_bytes(self, method, path):
        self.requests.append((method, path, None))
        return b"PNG"


class ComfyUIProviderTests(unittest.TestCase):
    def _workflow_repo(self, root):
        Path(root).mkdir(parents=True, exist_ok=True)
        source = Path(__file__).parents[1] / "data" / "image_workflows" / "basic_core.template.json"
        target = Path(root) / "basic_core.template.json"
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return WorkflowRepository(root)

    def _task(self):
        return ImageTask.create(
            save_id="测试",
            intent="scene_cg",
            provider_id="comfyui",
            workflow_id="builtin_basic",
            prompt={"positive": "a red cube", "negative": "blurry", "seed": 7},
            provider_options={"checkpoint": "test.safetensors"},
        )

    def test_builtin_workflow_maps_task_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            definition = self._workflow_repo(temp_dir).get("builtin_basic")
            rendered = definition.render(self._task())
            self.assertEqual(rendered["4"]["inputs"]["ckpt_name"], "test.safetensors")
            self.assertEqual(rendered["6"]["inputs"]["text"], "a red cube")
            self.assertEqual(rendered["3"]["inputs"]["seed"], 7)

    def test_builtin_workflow_generates_non_negative_seed_when_omitted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            task = self._task()
            task.prompt.seed = None
            rendered = self._workflow_repo(temp_dir).get("builtin_basic").render(task)
            self.assertGreaterEqual(rendered["3"]["inputs"]["seed"], 0)

    def test_workflow_allows_missing_optional_mapping_and_reports_risk(self):
        definition = WorkflowDefinition.from_dict({"id": "compatible", "workflow": {"1": {"inputs": {}, "class_type": "Test"}}, "mapping": {}})
        report = definition.mapping_report()
        self.assertTrue(report["can_submit"])
        self.assertFalse(report["can_inject_prompt"])
        self.assertIn("positive", report["warnings"])

    def test_workflow_still_rejects_broken_graph_reference(self):
        with self.assertRaises(WorkflowError):
            WorkflowDefinition.from_dict({"id": "bad", "workflow": {"1": {"inputs": {"model": ["404", 0]}, "class_type": "Test"}}})

    def test_unmapped_prompt_blocks_normal_generation_but_allows_original_test(self):
        definition = WorkflowDefinition.from_dict({
            "id": "raw", "workflow": {"1": {"inputs": {"value": 1}, "class_type": "CustomNode"}}
        })
        task = self._task()
        with self.assertRaises(WorkflowError):
            definition.render(task)
        self.assertEqual(definition.render(task, allow_original_prompt=True)["1"]["inputs"]["value"], 1)

    def test_import_raw_builtin_workflow_infers_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(__file__).parents[1] / "data" / "image_workflows" / "basic_core.template.json"
            raw = json.loads(source.read_text(encoding="utf-8"))["workflow"]
            definition = WorkflowRepository(temp_dir).import_definition(raw)
            self.assertEqual(definition.mapping["checkpoint"], ["4", "ckpt_name"])

    def test_imported_workflow_keeps_model_and_size_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(__file__).parents[1] / "data" / "image_workflows" / "basic_core.template.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["id"] = "custom"
            payload["workflow"]["4"]["inputs"]["ckpt_name"] = "workflow-model.safetensors"
            payload["workflow"]["5"]["inputs"]["width"] = 1024
            definition = WorkflowRepository(temp_dir).import_definition(payload)
            task = self._task()
            task.workflow_id = "custom"
            task.prompt.width = 512
            rendered = definition.render(task)
            self.assertEqual(rendered["4"]["inputs"]["ckpt_name"], "workflow-model.safetensors")
            self.assertEqual(rendered["5"]["inputs"]["width"], 1024)

    def test_profile_layers_prompts_and_only_applies_enabled_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(__file__).parents[1] / "data" / "image_workflows" / "basic_core.template.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["id"] = "layered"
            payload["workflow"]["6"]["inputs"]["text"] = "workflow quality"
            repo = WorkflowRepository(Path(temp_dir) / "workflows")
            definition = repo.import_definition(payload)
            WorkflowProfileRepository(definition.profile_root).save(definition.id, definition.fingerprint, {
                "allow_overrides": True,
                "overrides": {"width": 896},
                "player_positive": "player style",
                "player_negative": "player negative",
            })
            task = self._task()
            task.workflow_id = definition.id
            rendered = definition.render(task)
            self.assertEqual(rendered["6"]["inputs"]["text"], "workflow quality, a red cube, player style")
            self.assertEqual(rendered["7"]["inputs"]["text"], "blurry, player negative")
            self.assertEqual(rendered["5"]["inputs"]["width"], 896)

    def test_manual_mapping_enables_prompt_injection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = WorkflowRepository(Path(temp_dir) / "workflows")
            definition = repo.import_definition({
                "id": "manual",
                "name": "manual",
                "workflow": {"10": {"inputs": {"text": "base"}, "class_type": "CustomText"}},
            })
            WorkflowProfileRepository(definition.profile_root).save(definition.id, definition.fingerprint, {
                "mapping_overrides": {"positive": ["10", "text"]},
            })
            task = self._task()
            task.workflow_id = definition.id
            self.assertTrue(definition.mapping_report()["can_inject_prompt"])
            self.assertEqual(definition.render(task)["10"]["inputs"]["text"], "base, a red cube")

    def test_changed_workflow_disables_stale_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles = WorkflowProfileRepository(temp_dir)
            profiles.save("wf", "old", {"allow_overrides": True, "overrides": {"width": 999}})
            restored = profiles.get("wf", "new")
            self.assertFalse(restored.allow_overrides)
            self.assertEqual(restored.overrides, {})

    def test_prompt_composition_ignores_empty_layers(self):
        self.assertEqual(compose_prompt("base", "", "player"), "base, player")

    def test_check_reports_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeComfyUIProvider({
                ("GET", "/system_stats"): {"system": {}},
                ("GET", "/object_info/CheckpointLoaderSimple"): {
                    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a.safetensors", "b.ckpt"]]}}}
                },
            }, workflows=self._workflow_repo(temp_dir))
            result = provider.check()
            self.assertTrue(result.connected)
            self.assertEqual(result.checkpoints, ["a.safetensors", "b.ckpt"])

    def test_submit_and_fetch_completed_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            provider = FakeComfyUIProvider({
                ("POST", "/prompt"): {"prompt_id": "job_1"},
                ("GET", "/history/job_1"): {
                    "job_1": {"outputs": {"9": {"images": [{"filename": "result.png", "subfolder": "", "type": "output"}]}}}
                },
            }, workflows=self._workflow_repo(Path(temp_dir) / "workflows"), output_dir=output_dir)
            job = provider.submit(self._task())
            self.assertEqual(job.id, "job_1")
            completed = provider.query(job.id)
            self.assertEqual(completed.state, "succeeded")
            self.assertEqual(Path(completed.output_images[0]).read_bytes(), b"PNG")


if __name__ == "__main__":
    unittest.main()
