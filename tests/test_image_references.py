import base64
import tempfile
import unittest

from core.image_generation.references import ReferenceImageError, ReferenceImageRepository


PNG = b"\x89PNG\r\n\x1a\n" + b"test"


class ImageReferenceTests(unittest.TestCase):
    def test_save_and_reload_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_url = "data:image/png;base64," + base64.b64encode(PNG).decode()
            repository = ReferenceImageRepository(temp_dir)
            item = repository.add_data_url("角色.png", "character", data_url)
            self.assertEqual(item.mime_type, "image/png")
            self.assertEqual(repository.file_path(item.id).read_bytes(), PNG)

    def test_rejects_fake_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_url = "data:image/png;base64," + base64.b64encode(b"not an image").decode()
            with self.assertRaises(ReferenceImageError):
                ReferenceImageRepository(temp_dir).add_data_url("fake.png", "style", data_url)


if __name__ == "__main__":
    unittest.main()
