import unittest

from utils.asset_catalog import list_asset_names, resolve_template_path


class AssetCatalogTests(unittest.TestCase):
    def test_world_simulation_template_is_discoverable_without_personal_assets(self):
        template_path = resolve_template_path("entities", "世界推演")

        self.assertIsNotNone(template_path)
        self.assertTrue(template_path.is_file())
        self.assertIn("世界推演", list_asset_names("entities"))


if __name__ == "__main__":
    unittest.main()
