import tempfile
import unittest
from pathlib import Path

import yaml

from core.asset_lifecycle import AssetLifecycleError, clone_yaml_asset, find_yaml_asset, rename_yaml_asset


class AssetLifecycleTests(unittest.TestCase):
    def write(self, root, filename, data):
        path = Path(root) / filename
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_clone_is_independent_and_template_marker_is_removed(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.write(root, "hero.template.yml", {"name": "英雄模板", "tags": ["模板", "角色"], "is_template": True, "description": "原内容"})
            target = clone_yaml_asset(root, "英雄模板", "英雄分支")
            cloned = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertTrue(source.exists())
            self.assertEqual(cloned["name"], "英雄分支")
            self.assertNotIn("模板", cloned["tags"])
            self.assertNotIn("is_template", cloned)

    def test_rename_changes_internal_name_and_file_without_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.write(root, "old.yml", {"name": "旧名称", "content": "内容"})
            target = rename_yaml_asset(root, "旧名称", "新名称")
            self.assertFalse(source.exists())
            self.assertEqual(yaml.safe_load(target.read_text(encoding="utf-8"))["name"], "新名称")

    def test_casefold_conflict_and_template_rename_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "one.yml", {"name": "Alpha"})
            self.write(root, "two.yml", {"name": "Beta"})
            with self.assertRaises(AssetLifecycleError):
                clone_yaml_asset(root, "Alpha", "beta")
            template = self.write(root, "locked.template.yml", {"name": "锁定", "tags": ["模板"]})
            with self.assertRaises(AssetLifecycleError):
                rename_yaml_asset(root, "锁定", "新锁定")
            self.assertTrue(template.exists())

    def test_worldbook_clone_keeps_entries_but_changes_book_name(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "world.yml", {"name": "原世界", "entries": [{"name": "法律", "content": "规则"}]})
            target = clone_yaml_asset(root, "原世界", "分支世界", worldbook=True)
            cloned = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(cloned["name"], "分支世界")
            self.assertEqual(cloned["entries"][0]["name"], "法律")
            self.assertTrue(cloned["entries"][0]["id"])

    def test_find_by_name_does_not_depend_on_filename(self):
        with tempfile.TemporaryDirectory() as root:
            expected = self.write(root, "unrelated.yml", {"name": "中文资产"})
            self.assertEqual(find_yaml_asset(root, "中文资产"), expected)


if __name__ == "__main__":
    unittest.main()
