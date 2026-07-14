import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from api.v1.local_asset_routes import delete_local_asset
from core.image_generation.models import ImageTaskStatus
from core.image_generation.runtime import clear_image_runtimes, get_image_runtime
from core.session_manager import active_sessions


class LocalCharacterPortraitCleanupTests(unittest.TestCase):
    def tearDown(self):
        active_sessions.pop("portrait_cleanup", None)
        clear_image_runtimes()

    def test_deleting_local_character_deletes_owned_portrait_task_and_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "characters"
            characters.mkdir()
            runtime = get_image_runtime(root)
            task = runtime.service.create("测试", {
                "intent": "character_portrait",
                "prompt": {"positive": "hero"},
                "character_ids": ["主角"],
            })
            task.status = ImageTaskStatus.SUCCEEDED
            output = runtime.service.repository.outputs_dir / "portrait.png"
            output.write_bytes(b"image")
            task.output_images = [str(output)]
            runtime.service.repository.save(task)
            card = characters / "主角.yml"
            card.write_text(yaml.safe_dump({
                "name": "主角",
                "portrait": {"task_id": task.id, "image_index": 0},
            }, allow_unicode=True), encoding="utf-8")
            active_sessions["portrait_cleanup"] = SimpleNamespace(save_dir_path=str(root))

            result = delete_local_asset("portrait_cleanup", "characters", "主角")

            self.assertTrue(result["deleted_portrait"])
            self.assertFalse(card.exists())
            self.assertFalse(output.exists())
            self.assertIsNone(runtime.service.repository.get(task.id))


if __name__ == "__main__":
    unittest.main()
