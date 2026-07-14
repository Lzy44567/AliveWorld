import json
import tempfile
import unittest
from pathlib import Path

from core.image_generation.models import ImageTask
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.image_generation.workflows import WorkflowDefinition, WorkflowError, WorkflowRepository


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

    def test_workflow_rejects_missing_mapping(self):
        with self.assertRaises(WorkflowError):
            WorkflowDefinition.from_dict({"id": "bad", "workflow": {"1": {"inputs": {}, "class_type": "Test"}}, "mapping": {}})

    def test_import_raw_builtin_workflow_infers_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(__file__).parents[1] / "data" / "image_workflows" / "basic_core.template.json"
            raw = json.loads(source.read_text(encoding="utf-8"))["workflow"]
            definition = WorkflowRepository(temp_dir).import_definition(raw)
            self.assertEqual(definition.mapping["checkpoint"], ["4", "ckpt_name"])

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
