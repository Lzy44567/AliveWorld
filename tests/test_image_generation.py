import json
import tempfile
import unittest

from core.image_generation import ImageGenerationService, ImageTaskRepository
from core.image_generation.models import ImageIntent, ImageTaskStatus
from core.image_generation.service import ImageTaskError
from core.image_generation.executor import ImageTaskRunner
from core.image_generation.pipeline import ImageGenerationPipeline
from core.image_generation.providers.base import ProviderJob


class ImageGenerationTests(unittest.TestCase):
    def test_create_and_reload_ready_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            task = service.create("测试存档", {
                "intent": "scene_cg",
                "source_message_id": "message_1",
                "prompt": {
                    "positive": "a red cube on a white table",
                    "references": [{"path": "ref.png", "role": "style"}],
                },
            })

            self.assertEqual(task.intent, ImageIntent.SCENE_CG)
            self.assertEqual(task.status, ImageTaskStatus.READY)
            restored = ImageGenerationService(ImageTaskRepository(temp_dir)).get(task.id)
            self.assertEqual(restored.prompt.positive, "a red cube on a white table")
            self.assertEqual(restored.prompt.references[0].role, "style")

    def test_empty_prompt_stays_queued_for_prompt_compilation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            task = service.create("测试存档", {"intent": "character_portrait", "character_ids": ["角色甲"]})
            self.assertEqual(task.status, ImageTaskStatus.QUEUED)

    def test_cancel_and_retry_are_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            task = service.create("测试存档", {"intent": "scene_cg", "prompt": {"positive": "test"}})
            cancelled = service.cancel(task.id)
            self.assertEqual(cancelled.status, ImageTaskStatus.CANCELLED)
            retried = service.retry(task.id)
            self.assertEqual(retried.status, ImageTaskStatus.READY)
            self.assertEqual(service.get(task.id).status, ImageTaskStatus.READY)

    def test_invalid_intent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            with self.assertRaises(ImageTaskError):
                service.create("测试存档", {"intent": "unknown"})

    def test_repository_uses_atomic_versioned_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ImageTaskRepository(temp_dir)
            service = ImageGenerationService(repository)
            service.create("测试存档", {"intent": "scene_cg"})
            payload = json.loads(repository.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
            self.assertEqual(len(payload["tasks"]), 1)

    def test_generation_parameters_are_normalized_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            task = service.create("测试存档", {"intent": "scene_cg", "prompt": {"positive": "test", "width": 770, "height": 1025, "count": 9, "steps": 33, "cfg": 8.5}})
            self.assertEqual((task.prompt.width, task.prompt.height), (768, 1024))
            self.assertEqual(task.prompt.count, 4)
            self.assertEqual((task.prompt.steps, task.prompt.cfg), (33, 8.5))

    def test_regenerate_creates_new_task_and_delete_removes_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ImageTaskRepository(temp_dir)
            service = ImageGenerationService(repository)
            task = service.create("测试存档", {"intent": "scene_cg", "prompt": {"positive": "test"}})
            task.status = ImageTaskStatus.SUCCEEDED
            task.output_images = ["result.png"]
            (repository.outputs_dir / "result.png").write_bytes(b"image")
            repository.save(task)
            regenerated = service.regenerate(task.id)
            self.assertNotEqual(regenerated.id, task.id)
            self.assertEqual(regenerated.prompt.positive, "test")
            service.delete(task.id)
            self.assertIsNone(repository.get(task.id))
            self.assertFalse((repository.outputs_dir / "result.png").exists())

    def test_pipeline_compiles_then_starts_runner(self):
        class ImmediateProvider:
            id = "fake"
            def submit(self, task): return ProviderJob(id="job_2", state="submitted")
            def query(self, provider_job_id): return ProviderJob(id=provider_job_id, state="succeeded", progress=1, output_images=["compiled.png"])
            def cancel(self, provider_job_id): return True

        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            runner = ImageTaskRunner(service, lambda _task: ImmediateProvider(), poll_interval=0.001)
            task = service.create("测试存档", {"intent": "scene_cg"})
            ImageGenerationPipeline(service, runner).compile_and_start(task.id, lambda: {"positive": "compiled prompt", "negative": "bad", "notes": "ok"})
            for _ in range(100):
                if service.get(task.id).status == ImageTaskStatus.SUCCEEDED:
                    break
                __import__("time").sleep(0.005)
            completed = service.get(task.id)
            self.assertEqual(completed.prompt.positive, "compiled prompt")
            self.assertEqual(completed.status, ImageTaskStatus.SUCCEEDED)

    def test_background_runner_persists_success(self):
        class ImmediateProvider:
            id = "fake"
            def submit(self, task): return ProviderJob(id="job_1", state="submitted")
            def query(self, provider_job_id): return ProviderJob(id=provider_job_id, state="succeeded", progress=1, output_images=["result.png"])
            def cancel(self, provider_job_id): return True

        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageGenerationService(ImageTaskRepository(temp_dir))
            task = service.create("测试存档", {"intent": "scene_cg", "prompt": {"positive": "test"}})
            runner = ImageTaskRunner(service, lambda _task: ImmediateProvider(), poll_interval=0.001)
            self.assertTrue(runner.start(task.id))
            for _ in range(100):
                if service.get(task.id).status == ImageTaskStatus.SUCCEEDED:
                    break
                __import__("time").sleep(0.005)
            completed = service.get(task.id)
            self.assertEqual(completed.status, ImageTaskStatus.SUCCEEDED)
            self.assertEqual(completed.output_images, ["result.png"])


if __name__ == "__main__":
    unittest.main()
