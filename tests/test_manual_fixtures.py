import unittest
from pathlib import Path

import yaml


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "manual_assets"


class ManualFixtureTests(unittest.TestCase):
    def test_manual_fixture_cards_have_required_shapes(self):
        required_fields = {
            "worldbooks": {"name", "global_setting", "entries", "is_active"},
            "styles": {"name", "content", "is_active"},
            "characters": {"name", "description", "is_player", "is_active"},
            "entities": {"name", "motive", "status", "mechanisms", "is_active"},
        }

        for asset_type, fields in required_fields.items():
            files = list((FIXTURE_ROOT / asset_type).glob("*.yml"))
            self.assertEqual(len(files), 1, asset_type)
            data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
            self.assertTrue(fields <= set(data), f"{asset_type}: missing {fields - set(data)}")
            self.assertIn("测试夹具", data["tags"])
