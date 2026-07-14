import json
import tempfile
import unittest

from core.image_generation import ImageGenerationService, ImageTaskRepository
from core.image_generation.models import ImageIntent, ImageTaskStatus
from core.image_generation.service import ImageTaskError


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


if __name__ == "__main__":
    unittest.main()
