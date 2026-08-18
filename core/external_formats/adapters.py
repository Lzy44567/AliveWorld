"""Pure mappings from external character/lorebook objects to AliveWorld assets."""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any

from core.worldbook import normalize_worldbook

from .models import ExternalFormatError, ImportPreview
from .png import read_character_text_chunks


MAX_JSON_BYTES = 8 * 1024 * 1024


def _decode_json(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_JSON_BYTES:
        raise ExternalFormatError("外部资产超过 8 MB 安全限制")
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalFormatError("文件不是有效的 UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ExternalFormatError("外部资产 JSON 顶层必须是对象")
    return value


def parse_external_payload(payload: bytes, filename: str, kind: str = "auto") -> ImportPreview:
    suffix = Path(filename or "external.json").suffix.lower()
    portrait = None
    if suffix in {".png", ".apng"} or payload.startswith(b"\x89PNG"):
        if kind not in {"auto", "character"}:
            raise ExternalFormatError("PNG 只能作为外部角色卡导入")
        chunks = read_character_text_chunks(payload)
        keyword = "ccv3" if "ccv3" in chunks else "chara"
        try:
            decoded = base64.b64decode(chunks[keyword].strip(), validate=True)
        except (ValueError, TypeError) as exc:
            raise ExternalFormatError(f"PNG 的 {keyword} 元数据不是有效 Base64") from exc
        source = _decode_json(decoded)
        portrait = payload
        preview = adapt_character_card(source)
        preview.portrait_bytes = portrait
        if keyword == "chara" and "ccv3" not in chunks:
            preview.warnings.append("PNG 仅包含旧版 chara 元数据，已按 V2/V1 兼容模式读取。")
        return preview

    source = _decode_json(payload)
    detected = detect_format(source)
    if kind == "character" or (kind == "auto" and detected == "character"):
        return adapt_character_card(source)
    if kind == "lorebook" or (kind == "auto" and detected == "lorebook"):
        return adapt_lorebook(source, fallback_name=Path(filename).stem)
    raise ExternalFormatError("无法识别该 JSON；请选择角色卡或世界书类型并检查文件格式")


def detect_format(source: dict[str, Any]) -> str:
    if source.get("spec") in {"chara_card_v2", "chara_card_v3"}:
        return "character"
    if source.get("spec") == "lorebook_v3":
        return "lorebook"
    data = source.get("data")
    if isinstance(data, dict) and isinstance(data.get("name"), str) and any(
        key in data for key in ("first_mes", "personality", "scenario", "mes_example")
    ):
        return "character"
    if isinstance(source.get("entries"), (list, dict)):
        return "lorebook"
    if all(key in source for key in ("name", "description")):
        return "character"
    return "unknown"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def adapt_character_card(source: dict[str, Any]) -> ImportPreview:
    spec = _text(source.get("spec"))
    if spec and spec not in {"chara_card_v2", "chara_card_v3"}:
        raise ExternalFormatError(f"不支持的角色卡规范：{spec}")
    data = source.get("data") if isinstance(source.get("data"), dict) else source
    name = _text(data.get("name"))
    if not name:
        raise ExternalFormatError("角色卡缺少名称，无法导入")

    sections: list[str] = []
    description = _text(data.get("description"))
    if description:
        sections.append(description)
    for title, key in (("性格", "personality"), ("场景设定", "scenario"), ("对话示例", "mes_example")):
        value = _text(data.get(key))
        if value:
            sections.append(f"【{title}】\n{value}")

    tags = _list(data.get("tags"))
    mapped = ["name → 名称", "description → 背景与外观设定"]
    degraded: list[str] = []
    for key, label in (("personality", "性格"), ("scenario", "场景"), ("mes_example", "对话示例")):
        if _text(data.get(key)):
            degraded.append(f"{key} 已合并到角色描述的“{label}”分段")
    if _text(data.get("first_mes")):
        mapped.append("first_mes → 开场情景")
    if tags:
        mapped.append("tags → 玩家标签")

    known_native = {"name", "description", "personality", "scenario", "mes_example", "first_mes", "tags"}
    preserved = sorted(key for key, value in data.items() if key not in known_native and value not in (None, "", [], {}))
    if data.get("character_book"):
        degraded.append("character_book 已随来源元数据保留；AliveWorld 尚未把角色专属 Lorebook 自动载入正文")
    if _text(data.get("system_prompt")) or _text(data.get("post_history_instructions")):
        degraded.append("外部系统提示词已保留但不会自动取得 AliveWorld 系统权限")

    source_format = spec or "tavern_card_v1_compatible"
    version = _text(source.get("spec_version")) or ("1" if not spec else "unknown")
    asset = {
        "name": name,
        "tags": tags,
        "description": "\n\n".join(sections),
        "starting_scene": _text(data.get("first_mes")),
        "is_player": False,
        "_external_import": {
            "format": source_format,
            "version": version,
            "source": copy.deepcopy(source),
        },
    }
    warnings = []
    if spec == "chara_card_v3" and version not in {"3", "3.0"}:
        warnings.append(f"该卡声明 V3 版本 {version}；本版按已知字段尽力导入。")
    return ImportPreview(
        asset_type="characters",
        source_format=source_format,
        source_version=version,
        suggested_name=name,
        mapped_asset=asset,
        mapped_fields=mapped,
        degraded_fields=degraded,
        preserved_fields=preserved,
        warnings=warnings,
    )


def adapt_lorebook(source: dict[str, Any], fallback_name: str = "导入世界书") -> ImportPreview:
    spec = _text(source.get("spec"))
    if spec and spec != "lorebook_v3":
        raise ExternalFormatError(f"不支持的 Lorebook 规范：{spec}")
    data = source.get("data") if spec == "lorebook_v3" and isinstance(source.get("data"), dict) else source
    raw_entries = data.get("entries", [])
    if isinstance(raw_entries, dict):
        raw_entries = [dict(value, _source_uid=key) if isinstance(value, dict) else value for key, value in raw_entries.items()]
    if not isinstance(raw_entries, list):
        raise ExternalFormatError("Lorebook 的 entries 必须是数组或对象")

    entries = []
    degraded: list[str] = []
    preserved_entry_fields: set[str] = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            degraded.append(f"第 {index + 1} 个条目不是对象，已跳过")
            continue
        keys = raw.get("keys", raw.get("key", []))
        if isinstance(keys, str):
            keys = [keys]
        keys = _list(keys)
        secondary = raw.get("secondary_keys", raw.get("keysecondary", []))
        if isinstance(secondary, str):
            secondary = [secondary]
        secondary = _list(secondary)
        constant = bool(raw.get("constant", False))
        enabled = raw.get("enabled", not bool(raw.get("disable", False))) is not False
        entry_name = _text(raw.get("name") or raw.get("comment")) or f"导入条目 {index + 1}"
        tags = ["外部导入"]
        if constant:
            tags.append("常驻")
        if bool(raw.get("selective")) and secondary:
            degraded.append(f"“{entry_name}”的次要关键词/选择性条件已保留，但当前按普通关键词检索")
        if bool(raw.get("use_regex")):
            degraded.append(f"“{entry_name}”的正则触发已保留，但当前不会执行正则")
        native = {"keys", "key", "content", "enabled", "disable", "name", "comment", "constant"}
        preserved_entry_fields.update(key for key, value in raw.items() if key not in native and value not in (None, "", [], {}))
        entries.append({
            "id": str(raw.get("id", raw.get("uid", raw.get("_source_uid", "")))) or None,
            "name": entry_name,
            "keys": ", ".join(keys),
            "content": _text(raw.get("content")),
            "tags": tags,
            "is_active": enabled,
        })

    name = _text(data.get("name")) or _text(fallback_name) or "导入世界书"
    description = _text(data.get("description"))
    top_native = {"name", "description", "entries"}
    preserved = sorted(key for key, value in data.items() if key not in top_native and value not in (None, "", [], {}))
    preserved.extend(f"entries[].{key}" for key in sorted(preserved_entry_fields))
    asset = normalize_worldbook({
        "name": name,
        "tags": ["外部导入"],
        "overview": description,
        "axioms": [],
        "entries": entries,
        "_external_import": {
            "format": spec or "sillytavern_lorebook_compatible",
            "version": "3" if spec == "lorebook_v3" else "unknown",
            "source": copy.deepcopy(source),
        },
    })
    mapped = ["name/文件名 → 世界书名称", "description → 世界概述", f"entries → {len(entries)} 个世界书条目"]
    if any("常驻" in entry["tags"] for entry in entries):
        mapped.append("constant → 常驻标签")
    return ImportPreview(
        asset_type="worldbooks",
        source_format=spec or "sillytavern_lorebook_compatible",
        source_version="3" if spec == "lorebook_v3" else "unknown",
        suggested_name=name,
        mapped_asset=asset,
        mapped_fields=mapped,
        degraded_fields=degraded,
        preserved_fields=list(dict.fromkeys(preserved)),
        warnings=[] if entries else ["该世界书没有可导入条目。"],
    )
