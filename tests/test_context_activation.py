import tempfile
import unittest
from pathlib import Path

import yaml

from core.context_manager import ContextManager


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class ContextActivationTests(unittest.TestCase):
    def test_inactive_worldbook_style_and_character_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_dir = Path(temp_dir)
            write_yaml(save_dir / "worldbooks" / "active.yml", {
                "name": "启用世界书", "global_setting": "世界开启", "is_active": True,
                "entries": [{"name": "启用条目", "keys": "激活词", "content": "条目开启"}],
            })
            write_yaml(save_dir / "worldbooks" / "inactive.yml", {
                "name": "封存世界书", "global_setting": "世界关闭", "is_active": False,
                "entries": [{"name": "封存条目", "keys": "激活词", "content": "条目关闭"}],
            })
            write_yaml(save_dir / "styles" / "active.yml", {"name": "启用文风", "content": "文风开启", "is_active": True})
            write_yaml(save_dir / "styles" / "inactive.yml", {"name": "封存文风", "content": "文风关闭", "is_active": False})
            write_yaml(save_dir / "characters" / "active.yml", {"name": "启用角色", "description": "角色开启", "is_player": True, "is_active": True})
            write_yaml(save_dir / "characters" / "inactive.yml", {"name": "封存角色", "description": "角色关闭", "is_player": True, "is_active": False})

            context = ContextManager()
            context.refresh_from_local(str(save_dir), "")
            active_world, triggered = context.build_active_world_info("", "激活词", "账本")

            self.assertIn("世界开启", active_world)
            self.assertNotIn("世界关闭", active_world)
            self.assertIn("文风开启", context.style_info)
            self.assertNotIn("文风关闭", context.style_info)
            self.assertIn("角色开启", context.char_info)
            self.assertNotIn("角色关闭", context.char_info)
            self.assertEqual(triggered, ["启用条目"])
            self.assertIn("条目开启", active_world)
            self.assertNotIn("条目关闭", active_world)

            visible_world, _ = context.build_visible_world_info("", "激活词")
            self.assertIn("条目开启", visible_world)
            self.assertNotIn("隐藏的暗流因果", visible_world)
            self.assertNotIn("账本", visible_world)


if __name__ == "__main__":
    unittest.main()
