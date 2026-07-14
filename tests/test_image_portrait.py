import tempfile
import unittest
from pathlib import Path

import yaml
from unittest.mock import patch

from core.image_generation.models import ImageTask, ImageTaskStatus
from core.image_generation.portrait import PortraitAssignmentError, assign_current_portrait, assign_global_portrait


class ImagePortraitTests(unittest.TestCase):
    def test_assigns_successful_portrait_to_local_character(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "characters"
            directory.mkdir()
            path = directory / "hero.yml"
            path.write_text(yaml.safe_dump({"name": "主角", "description": "剑士"}, allow_unicode=True), encoding="utf-8")
            task = ImageTask.create(save_id="测试", intent="character_portrait", provider_id="comfyui", workflow_id="builtin_basic", prompt={"positive": "hero"}, character_ids=["主角"])
            task.status = ImageTaskStatus.SUCCEEDED
            task.output_images = ["portrait.png"]
            result = assign_current_portrait(temp_dir, "主角", task)
            self.assertEqual(result["portrait"]["task_id"], task.id)
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["portrait"]["image_index"], 0)

    def test_rejects_wrong_character_or_unfinished_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "characters"
            directory.mkdir()
            (directory / "hero.yml").write_text("name: 主角\n", encoding="utf-8")
            task = ImageTask.create(save_id="测试", intent="character_portrait", provider_id="comfyui", workflow_id="builtin_basic", prompt={"positive": "hero"}, character_ids=["主角"])
            with self.assertRaises(PortraitAssignmentError):
                assign_current_portrait(temp_dir, "主角", task)
            task.status = ImageTaskStatus.SUCCEEDED
            task.output_images = ["portrait.png"]
            with self.assertRaises(PortraitAssignmentError):
                assign_current_portrait(temp_dir, "其他角色", task)

    def test_global_portrait_is_copied_out_of_save_task_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "global_characters"
            outputs = root / "save_outputs"
            characters.mkdir()
            outputs.mkdir()
            card = characters / "hero.yml"
            card.write_text("name: 主角\n", encoding="utf-8")
            (outputs / "portrait.png").write_bytes(b"image")
            task = ImageTask.create(save_id="测试", intent="character_portrait", provider_id="comfyui", workflow_id="builtin_basic", prompt={"positive": "hero"}, character_ids=["主角"])
            task.status = ImageTaskStatus.SUCCEEDED
            task.output_images = [str(outputs / "portrait.png")]
            with patch("core.image_generation.portrait.CHAR_DIR", str(characters)):
                result = assign_global_portrait("主角", task, outputs)
            copied = characters / "_portraits" / result["portrait"]["path"]
            self.assertTrue(copied.is_file())
            self.assertEqual(result["portrait"]["scope"], "global")


if __name__ == "__main__":
    unittest.main()
