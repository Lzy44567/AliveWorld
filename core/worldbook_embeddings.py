"""Optional local embeddings for worldbook retrieval with safe fallback."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import multiprocessing
import shutil
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
DOWNLOAD_STATUS_FILE = Path(DATA_DIR) / "cache" / "worldbook_embedding_download.json"
ESTIMATED_DOWNLOAD_BYTES = 486 * 1024 * 1024


def _download_model_process(model_name: str, model_dir: str, status_file: str) -> None:
    status_path = Path(status_file)
    try:
        from huggingface_hub import snapshot_download
        Path(model_dir).mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=model_name,
            local_dir=model_dir,
            allow_patterns=[
                "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                "special_tokens_map.json", "sentencepiece.bpe.model", "unigram.json",
            ],
        )
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps({"state": "complete", "error": ""}), encoding="utf-8")
    except Exception as exc:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps({"state": "error", "error": str(exc)}, ensure_ascii=False), encoding="utf-8")


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
        self._download_process = None
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
        return all((self.model_dir / name).exists() for name in ("config.json", "model.safetensors", "tokenizer.json"))

    def status(self) -> dict[str, Any]:
        runtime_available = all(importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "huggingface_hub"))
        if self._download_process is not None and not self._download_process.is_alive():
            self._download_process.join(timeout=0.1)
            self._download_process = None
            if self.is_downloaded():
                self.enabled, self.state, self.error = True, "ready", ""
                self._save_settings()
            else:
                try:
                    result = json.loads(DOWNLOAD_STATUS_FILE.read_text(encoding="utf-8"))
                    self.state, self.error = result.get("state", "error"), result.get("error", "")
                except (OSError, ValueError):
                    self.state = "paused"
        downloaded_bytes = 0
        if self.model_dir.exists():
            for path in self.model_dir.rglob("*"):
                try:
                    if path.is_file(): downloaded_bytes += path.stat().st_size
                except OSError:
                    continue
        return {
            "enabled": self.enabled,
            "state": self.state,
            "model_name": self.model_name,
            "downloaded": self.is_downloaded(),
            "error": self.error,
            "downloaded_bytes": downloaded_bytes,
            "estimated_bytes": ESTIMATED_DOWNLOAD_BYTES,
            "progress": min(100, round(downloaded_bytes / ESTIMATED_DOWNLOAD_BYTES * 100, 1)) if ESTIMATED_DOWNLOAD_BYTES else 0,
            "model_dir": str(self.model_dir.resolve()),
            "source_url": f"https://huggingface.co/{self.model_name}",
            "runtime_note": "无需独立显卡；CPU可运行，建议至少预留2GB可用内存。",
            "runtime_available": runtime_available,
        }

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.enabled = bool(enabled)
        self.state = "ready" if self.enabled and self.is_downloaded() else ("missing" if self.enabled else "disabled")
        self._save_settings()
        return self.status()

    def download_in_background(self) -> dict[str, Any]:
        if not all(importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "huggingface_hub")):
            self.state = "error"
            self.error = "缺少本地语义依赖，请运行 install_windows.bat 并选择安装可选语义依赖。"
            return self.status()
        if self._download_process is not None and self._download_process.is_alive():
            return self.status()
        self.state, self.error = "downloading", ""
        DOWNLOAD_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_STATUS_FILE.write_text(json.dumps({"state": "downloading", "error": ""}), encoding="utf-8")
        self._download_process = multiprocessing.Process(
            target=_download_model_process,
            args=(self.model_name, str(self.model_dir), str(DOWNLOAD_STATUS_FILE)),
            name="worldbook-embedding-download",
            daemon=True,
        )
        self._download_process.start()
        return self.status()

    def pause_download(self) -> dict[str, Any]:
        if self._download_process is not None and self._download_process.is_alive():
            self._download_process.terminate()
            self._download_process.join(timeout=3)
        self._download_process = None
        self.state, self.error = "paused", ""
        return self.status()

    def uninstall(self) -> dict[str, Any]:
        self.pause_download()
        with self._lock:
            self._tokenizer = None
            self._model = None
        self.enabled = False
        if self.model_dir.exists():
            shutil.rmtree(self.model_dir)
        if self.cache.path.exists():
            self.cache.path.unlink()
        self.cache.items = {}
        self.state, self.error = "missing", ""
        self._save_settings()
        return self.status()

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
