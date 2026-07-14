import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from api.v1.local_asset_routes import LocalAssetUpdatePayload, update_local_asset
from api.v1.lobby_routes import AssetPayload, save_asset
from core.session_manager import active_sessions


class AssetMetadataPreservationTests(unittest.TestCase):
    def test_local_character_edit_preserves_portrait_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            characters = Path(temp_dir) / "characters"
            characters.mkdir()
            path = characters / "角色甲.yml"
            portrait = {"task_id": "image_1", "image_index": 0}
            path.write_text(yaml.safe_dump({"name": "角色甲", "description": "旧描述", "portrait": portrait}, allow_unicode=True), encoding="utf-8")
            active_sessions["metadata_test"] = SimpleNamespace(save_dir_path=temp_dir)
            try:
                update_local_asset("metadata_test", "characters", "角色甲", LocalAssetUpdatePayload(parsed_data={"name": "角色甲", "description": "新描述"}))
            finally:
                active_sessions.pop("metadata_test", None)
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["description"], "新描述")
            self.assertEqual(saved["portrait"], portrait)

    def test_global_character_edit_preserves_portrait_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "角色甲.yml"
            portrait = {"scope": "global", "path": "portrait.png"}
            path.write_text(yaml.safe_dump({"name": "角色甲", "description": "旧描述", "portrait": portrait}, allow_unicode=True), encoding="utf-8")
            with patch("api.v1.lobby_routes.resolve_asset_path", return_value=path), patch("api.v1.lobby_routes.resolve_template_path", return_value=None):
                asyncio.run(save_asset("characters", "角色甲", AssetPayload(parsed_data={"name": "角色甲", "description": "新描述"}, overwrite=True)))
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["description"], "新描述")
            self.assertEqual(saved["portrait"], portrait)


if __name__ == "__main__":
    unittest.main()
