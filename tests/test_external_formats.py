import base64
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import yaml

from core.external_formats import ExternalAssetImportService, ExternalFormatError


def _card(version="v2"):
    return {
        "spec": f"chara_card_{version}",
        "spec_version": "3.0" if version == "v3" else "2.0",
        "data": {
            "name": "外部测试角色",
            "description": "银发剑士。",
            "personality": "谨慎而诚实。",
            "scenario": "守卫北境。",
            "first_mes": "风雪中，她抬起头。",
            "mes_example": "{{char}}：不要靠近裂谷。",
            "tags": ["奇幻", "测试"],
            "system_prompt": "保持角色一致。",
            "alternate_greetings": ["另一种开场"],
            "character_book": {"entries": [{"keys": ["裂谷"], "content": "古老裂谷"}]},
            "extensions": {"example/plugin": {"value": 1}},
            **({"assets": [{"type": "icon", "uri": "ccdefault:", "name": "main", "ext": "png"}], "group_only_greetings": []} if version == "v3" else {}),
        },
    }


def _png_with_text(chunks):
    payload = b"\x89PNG\r\n\x1a\n"
    for keyword, value in chunks:
        body = keyword.encode("ascii") + b"\0" + value
        kind = b"tEXt"
        payload += struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    kind = b"IEND"
    payload += struct.pack(">I", 0) + kind + struct.pack(">I", zlib.crc32(kind) & 0xFFFFFFFF)
    return payload


class ExternalFormatTests(unittest.TestCase):
    def test_v2_character_mapping_preserves_non_native_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ExternalAssetImportService(Path(temp) / "data")
            payload = json.dumps(_card("v2"), ensure_ascii=False).encode()
            preview = service.inspect(payload, "card.json", "character")
            self.assertEqual(preview.asset_type, "characters")
            self.assertIn("【性格】", preview.mapped_asset["description"])
            self.assertEqual(preview.mapped_asset["starting_scene"], "风雪中，她抬起头。")
            self.assertIn("character_book", preview.preserved_fields)
            self.assertTrue(any("系统提示词" in item for item in preview.degraded_fields))

    def test_png_prefers_ccv3_and_becomes_global_portrait(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ExternalAssetImportService(Path(temp) / "data")
            old = _card("v2")
            old["data"]["name"] = "不应采用旧卡"
            png = _png_with_text([
                ("chara", base64.b64encode(json.dumps(old).encode())),
                ("ccv3", base64.b64encode(json.dumps(_card("v3"), ensure_ascii=False).encode())),
            ])
            result = service.commit(png, "portrait.png", "character")
            saved = yaml.safe_load(Path(result["path"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["name"], "外部测试角色")
            self.assertEqual(saved["portrait"]["scope"], "global")
            self.assertTrue((Path(temp) / "data" / "characters" / "_portraits" / saved["portrait"]["path"]).is_file())
            self.assertEqual(saved["_external_import"]["format"], "chara_card_v3")

    def test_lorebook_maps_st_entries_and_reports_advanced_behaviour(self):
        source = {
            "name": "外部知识库",
            "description": "导入测试",
            "scanDepth": 4,
            "entries": {
                "7": {
                    "uid": 7,
                    "comment": "北境裂谷",
                    "key": ["裂谷", "北境"],
                    "keysecondary": ["风雪"],
                    "selective": True,
                    "content": "裂谷会吞噬声音。",
                    "constant": True,
                    "disable": False,
                    "order": 100,
                }
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            service = ExternalAssetImportService(Path(temp) / "data")
            preview = service.inspect(json.dumps(source, ensure_ascii=False).encode(), "north.json", "lorebook")
            entry = preview.mapped_asset["entries"][0]
            self.assertEqual(entry["name"], "北境裂谷")
            self.assertEqual(entry["keys"], "裂谷, 北境")
            self.assertIn("常驻", entry["tags"])
            self.assertIn("entries[].keysecondary", preview.preserved_fields)
            self.assertTrue(any("次要关键词" in item for item in preview.degraded_fields))

    def test_duplicate_name_is_blocked_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ExternalAssetImportService(Path(temp) / "data")
            payload = json.dumps(_card(), ensure_ascii=False).encode()
            service.commit(payload, "first.json", "character")
            with self.assertRaisesRegex(ExternalFormatError, "同名资产"):
                service.commit(payload, "second.json", "character")

    def test_invalid_and_oversized_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ExternalAssetImportService(Path(temp) / "data")
            with self.assertRaisesRegex(ExternalFormatError, "有效"):
                service.inspect(b"not-json", "bad.json", "character")
            with self.assertRaisesRegex(ExternalFormatError, "8 MB"):
                service.inspect(b"{" + b" " * (8 * 1024 * 1024), "large.json", "character")


if __name__ == "__main__":
    unittest.main()
