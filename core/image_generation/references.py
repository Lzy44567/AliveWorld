"""Managed per-save reference images."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


MAX_REFERENCE_BYTES = 12 * 1024 * 1024
MAGIC_TYPES = {
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"RIFF": ("image/webp", ".webp"),
}


class ReferenceImageError(ValueError):
    pass


@dataclass
class ReferenceImageAsset:
    id: str
    filename: str
    role: str
    mime_type: str
    stored_name: str
    created_at: str

    @classmethod
    def from_dict(cls, data):
        return cls(**{key: str(data.get(key, "")) for key in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)


class ReferenceImageRepository:
    def __init__(self, save_dir: str | Path):
        self.root = Path(save_dir) / "images" / "references"
        self.path = self.root / "references.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[ReferenceImageAsset]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReferenceImageError(f"参考图索引无法读取: {exc}") from exc
        return [ReferenceImageAsset.from_dict(item) for item in payload.get("references", []) if isinstance(item, dict)]

    def get(self, reference_id: str) -> ReferenceImageAsset:
        for item in self.list():
            if item.id == reference_id:
                return item
        raise ReferenceImageError("参考图不存在")

    def file_path(self, reference_id: str) -> Path:
        item = self.get(reference_id)
        path = (self.root / Path(item.stored_name).name).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ReferenceImageError("参考图路径无效") from exc
        return path

    def add_data_url(self, filename: str, role: str, data_url: str) -> ReferenceImageAsset:
        match = re.fullmatch(r"data:([^;,]+);base64,(.+)", str(data_url), flags=re.DOTALL)
        if not match:
            raise ReferenceImageError("参考图必须使用 Base64 data URL")
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ReferenceImageError("参考图 Base64 无效") from exc
        if not raw or len(raw) > MAX_REFERENCE_BYTES:
            raise ReferenceImageError("参考图为空或超过 12 MB")
        mime_type, extension = self._detect(raw)
        reference_id = f"reference_{uuid4().hex[:12]}"
        stored_name = f"{reference_id}{extension}"
        (self.root / stored_name).write_bytes(raw)
        item = ReferenceImageAsset(
            id=reference_id,
            filename=Path(str(filename or stored_name)).name,
            role=str(role or "character"),
            mime_type=mime_type,
            stored_name=stored_name,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        items = self.list()
        items.append(item)
        self._write(items)
        return item

    def remove(self, reference_id: str) -> ReferenceImageAsset:
        items = self.list()
        selected = next((item for item in items if item.id == reference_id), None)
        if not selected:
            raise ReferenceImageError("参考图不存在")
        path = self.file_path(reference_id)
        if path.exists():
            path.unlink()
        self._write([item for item in items if item.id != reference_id])
        return selected

    def _write(self, items: list[ReferenceImageAsset]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"version": 1, "references": [item.to_dict() for item in items]}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.path)

    @staticmethod
    def _detect(raw: bytes) -> tuple[str, str]:
        for magic, result in MAGIC_TYPES.items():
            if raw.startswith(magic):
                if magic == b"RIFF" and raw[8:12] != b"WEBP":
                    continue
                return result
        raise ReferenceImageError("只支持真实的 PNG、JPEG 或 WebP 图片")
