"""Optional local embeddings for worldbook retrieval with safe fallback."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Callable

from utils.file_io import DATA_DIR
from utils.sys_logger import get_logger


log = get_logger()
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_DIR = Path(DATA_DIR) / "models" / "worldbook_embedding"
CACHE_FILE = Path(DATA_DIR) / "cache" / "worldbook_embeddings.json"
SETTINGS_FILE = Path(DATA_DIR) / "worldbook_embedding_settings.json"


class VectorCache:
    def __init__(self, path: Path = CACHE_FILE):
        self.path = Path(path)
        self.items: dict[str, list[float]] = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self.items = {}

    @staticmethod
    def key(model_name: str, text: str) -> str:
        return hashlib.sha256(f"{model_name}\n{text}".encode("utf-8")).hexdigest()

    def get(self, model_name: str, text: str):
        return self.items.get(self.key(model_name, text))

    def put(self, model_name: str, text: str, vector: list[float]) -> None:
        self.items[self.key(model_name, text)] = vector

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")


class LocalEmbeddingManager:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        model_dir: Path = MODEL_DIR,
        cache: VectorCache | None = None,
        encoder: Callable[[list[str]], list[list[float]]] | None = None,
        settings_file: Path = SETTINGS_FILE,
    ):
        self.model_name = model_name
        self.model_dir = Path(model_dir)
        self.cache = cache or VectorCache()
        self._custom_encoder = encoder
        self.settings_file = Path(settings_file)
        self.enabled = False
        self.state = "disabled"
        self.error = ""
        self._tokenizer = None
        self._model = None
        self._lock = threading.RLock()
        self._load_settings()

    def _load_settings(self) -> None:
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            self.enabled = bool(data.get("enabled", False))
            self.model_name = str(data.get("model_name") or self.model_name)
        except (OSError, ValueError):
            pass
        if self.enabled:
            self.state = "ready" if self.is_downloaded() else "missing"

    def _save_settings(self) -> None:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps({"enabled": self.enabled, "model_name": self.model_name}, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_downloaded(self) -> bool:
        if self._custom_encoder:
            return True
        return (self.model_dir / "config.json").exists()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "model_name": self.model_name,
            "downloaded": self.is_downloaded(),
            "error": self.error,
        }

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.enabled = bool(enabled)
        self.state = "ready" if self.enabled and self.is_downloaded() else ("missing" if self.enabled else "disabled")
        self._save_settings()
        return self.status()

    def download_in_background(self) -> dict[str, Any]:
        if self.state == "downloading":
            return self.status()
        self.state, self.error = "downloading", ""
        thread = threading.Thread(target=self._download, name="worldbook-embedding-download", daemon=True)
        thread.start()
        return self.status()

    def _download(self) -> None:
        try:
            from transformers import AutoModel, AutoTokenizer
            self.model_dir.mkdir(parents=True, exist_ok=True)
            tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=False)
            model = AutoModel.from_pretrained(self.model_name, trust_remote_code=False)
            tokenizer.save_pretrained(self.model_dir)
            model.save_pretrained(self.model_dir)
            with self._lock:
                self._tokenizer, self._model = tokenizer, model.eval()
                self.enabled, self.state, self.error = True, "ready", ""
                self._save_settings()
            log.info("世界书本地嵌入模型已就绪: %s", self.model_name)
        except Exception as exc:
            self.state, self.error = "error", str(exc)
            log.warning("世界书嵌入模型下载失败，继续使用关键词降级: %s", exc)

    def _ensure_loaded(self) -> bool:
        if self._custom_encoder:
            return True
        if self._model is not None and self._tokenizer is not None:
            return True
        if not self.is_downloaded():
            self.state = "missing"
            return False
        try:
            from transformers import AutoModel, AutoTokenizer
            with self._lock:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir, local_files_only=True, trust_remote_code=False)
                self._model = AutoModel.from_pretrained(self.model_dir, local_files_only=True, trust_remote_code=False).eval()
            self.state, self.error = "ready", ""
            return True
        except Exception as exc:
            self.state, self.error = "error", str(exc)
            log.warning("世界书嵌入模型加载失败，使用关键词降级: %s", exc)
            return False

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if self._custom_encoder:
            return self._custom_encoder(texts)
        import torch
        encoded = self._tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            output = self._model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).expand(output.size()).float()
            pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.cpu().tolist()

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float] | None] = [self.cache.get(self.model_name, text) for text in texts]
        missing_indices = [index for index, value in enumerate(vectors) if value is None]
        if missing_indices:
            generated = self._encode([texts[index] for index in missing_indices])
            for index, vector in zip(missing_indices, generated):
                vectors[index] = vector
                self.cache.put(self.model_name, texts[index], vector)
            self.cache.save()
        return [value or [] for value in vectors]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))

    def scores(self, query: str, entries: list[dict[str, Any]]) -> dict[str, float]:
        if not self.enabled or not query.strip() or not self._ensure_loaded():
            return {}
        try:
            texts = [query] + [f"{item.get('name', '')}\n{item.get('content', '')}\n{' '.join(item.get('tags', []))}" for item in entries]
            vectors = self._vectors(texts)
            query_vector = vectors[0]
            return {item["id"]: self._cosine(query_vector, vector) for item, vector in zip(entries, vectors[1:])}
        except Exception as exc:
            self.state, self.error = "error", str(exc)
            log.warning("世界书语义检索失败，当前回合使用关键词降级: %s", exc)
            return {}


embedding_manager = LocalEmbeddingManager()
