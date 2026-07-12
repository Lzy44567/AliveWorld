import tempfile
import unittest
from pathlib import Path

from core.worldbook_embeddings import LocalEmbeddingManager, VectorCache


class WorldbookEmbeddingTests(unittest.TestCase):
    def test_disabled_manager_returns_empty_scores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LocalEmbeddingManager(
                cache=VectorCache(Path(temp_dir) / "cache.json"),
                encoder=lambda texts: [[1.0, 0.0] for _ in texts],
                settings_file=Path(temp_dir) / "settings.json",
            )
            self.assertEqual(manager.scores("学校", [{"id": "one", "name": "学校", "content": "课程", "tags": []}]), {})

    def test_enabled_manager_scores_and_caches_vectors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []
            def encode(texts):
                calls.append(list(texts))
                return [[1.0, 0.0] if "学校" in text else [0.0, 1.0] for text in texts]

            cache_path = Path(temp_dir) / "cache.json"
            manager = LocalEmbeddingManager(
                cache=VectorCache(cache_path), encoder=encode,
                settings_file=Path(temp_dir) / "settings.json",
            )
            manager.set_enabled(True)
            entries = [
                {"id": "school", "name": "学校", "content": "课程", "tags": []},
                {"id": "desert", "name": "沙漠", "content": "风沙", "tags": []},
            ]
            scores = manager.scores("进入学校", entries)
            self.assertEqual(scores["school"], 1.0)
            self.assertEqual(scores["desert"], 0.0)
            self.assertTrue(cache_path.exists())
            manager.scores("进入学校", entries)
            self.assertEqual(len(calls), 1)

    def test_encoder_failure_degrades_without_raising(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            def fail(_texts): raise RuntimeError("测试失败")
            manager = LocalEmbeddingManager(
                cache=VectorCache(Path(temp_dir) / "cache.json"), encoder=fail,
                settings_file=Path(temp_dir) / "settings.json",
            )
            manager.set_enabled(True)
            self.assertEqual(manager.scores("学校", [{"id": "one", "name": "学校", "content": "", "tags": []}]), {})
            self.assertEqual(manager.state, "error")

    def test_uninstall_removes_model_and_vector_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_dir = root / "model"
            model_dir.mkdir()
            for name in ("config.json", "model.safetensors", "tokenizer.json"):
                (model_dir / name).write_text("test", encoding="utf-8")
            cache = VectorCache(root / "cache.json")
            cache.put("model", "text", [1.0])
            cache.save()
            manager = LocalEmbeddingManager(
                model_dir=model_dir, cache=cache, encoder=None,
                settings_file=root / "settings.json",
            )
            result = manager.uninstall()
            self.assertFalse(model_dir.exists())
            self.assertFalse(cache.path.exists())
            self.assertFalse(result["enabled"])


if __name__ == "__main__":
    unittest.main()
