"""Stable prompt slices, versioned local overrides, and request manifests."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from core.action_suggestions import action_suggestion_instruction
from core.player_agency import player_agency_instruction
from core.prompts import load_system_prompts
from core.story_continuity import continuity_instruction
from core.story_length import story_length_instruction
from utils.runtime_paths import PATHS


@dataclass(frozen=True)
class PromptSlice:
    id: str
    task: str
    title: str
    slot: str
    priority: int
    description: str
    editable: bool
    variables: tuple[str, ...]
    default_factory: Callable[[], str]


def _yaml_prompt(key: str) -> Callable[[], str]:
    return lambda: str(load_system_prompts().get(key, "") or "")


SLICES: tuple[PromptSlice, ...] = (
    PromptSlice("story.future.core", "story.future", "近期未来核心", "system", 100,
                "生成候选未来、行动裁定与暗流条件判断。", True,
                ("world_info", "character_info"), _yaml_prompt("reaction_prompt")),
    PromptSlice("story.future.player_agency", "story.future", "玩家行动权", "system", 200,
                "区分玩家可确定事实与需要世界裁定的外部结果。", True, (),
                lambda: player_agency_instruction()),
    PromptSlice("story.future.continuity", "story.future", "剧情连续性", "system", 300,
                "约束信息通道、客观事实与外部介入。", True, (), continuity_instruction),
    PromptSlice("story.settlement.core", "story.settlement", "正文结算核心", "system", 100,
                "续写正文并返回状态、世界书捕获等结构字段。", True,
                ("style_info", "world_info", "character_info"),
                _yaml_prompt("settlement_prompt")),
    PromptSlice("story.settlement.player_agency", "story.settlement", "玩家行动权", "system", 200,
                "禁止正文替玩家新增重大决定。", True, (),
                lambda: player_agency_instruction(require_output=False)),
    PromptSlice("story.settlement.continuity", "story.settlement", "剧情连续性", "system", 300,
                "保持事实、信息通道和场景对象连续。", True, (), continuity_instruction),
    PromptSlice("story.settlement.length", "story.settlement", "正文篇幅", "system", 500,
                "根据单局设置动态生成篇幅要求。", False, ("target_story_length",),
                lambda: story_length_instruction(500)),
    PromptSlice("story.settlement.suggestions", "story.settlement", "快捷行动", "system", 800,
                "仅在启用快捷行动按钮时动态加入。", False, ("enabled",),
                lambda: action_suggestion_instruction(True)),
    PromptSlice("world.capture.runtime", "world.capture", "世界观设定捕获", "system", 100,
                "当前由世界书捕获模块维护；尚未迁移到可编辑注册表。", False, (), lambda: ""),
    PromptSlice("workshop.runtime", "workshop", "工坊协作", "system", 100,
                "当前由各工坊模块维护；尚未迁移到可编辑注册表。", False, (), lambda: ""),
)

SLICE_BY_ID = {item.id: item for item in SLICES}
_VARIABLE_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class PromptOverrideStore:
    def __init__(self, path: Path | None = None):
        self.path = path or PATHS.data_dir / "developer" / "prompt_overrides.json"

    def _read(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"overrides": {}}
        except (OSError, json.JSONDecodeError):
            return {"overrides": {}}

    def get(self, slice_id: str) -> dict | None:
        value = self._read().get("overrides", {}).get(slice_id)
        return value if isinstance(value, dict) else None

    def save(self, slice_id: str, content: str) -> dict:
        definition = require_slice(slice_id)
        if not definition.editable:
            raise ValueError("此提示词切片尚不可编辑")
        validate_template(definition, content)
        data = self._read()
        overrides = data.setdefault("overrides", {})
        previous = overrides.get(slice_id) if isinstance(overrides.get(slice_id), dict) else {}
        record = {"version": int(previous.get("version", 0)) + 1, "content": content}
        overrides[slice_id] = record
        _atomic_json(self.path, data)
        return record

    def restore(self, slice_id: str) -> bool:
        data = self._read()
        overrides = data.setdefault("overrides", {})
        existed = slice_id in overrides
        overrides.pop(slice_id, None)
        if existed:
            _atomic_json(self.path, data)
        return existed


def require_slice(slice_id: str) -> PromptSlice:
    try:
        return SLICE_BY_ID[slice_id]
    except KeyError as exc:
        raise KeyError("未知提示词切片") from exc


def template_variables(content: str) -> set[str]:
    return set(_VARIABLE_RE.findall(content))


def validate_template(definition: PromptSlice, content: str) -> None:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("提示词不能为空")
    actual = template_variables(content)
    allowed = set(definition.variables)
    unknown = actual - allowed
    missing = allowed - actual
    if unknown:
        raise ValueError("包含未知变量：" + "、".join(sorted(unknown)))
    if missing:
        raise ValueError("缺少必要变量：" + "、".join(sorted(missing)))


def _estimate_tokens(text: str) -> int:
    # Conservative dependency-free estimate; UI labels it explicitly as an estimate.
    return max(1, math.ceil(len(text.encode("utf-8")) / 3.2)) if text else 0


def slice_view(definition: PromptSlice, store: PromptOverrideStore | None = None) -> dict:
    store = store or PromptOverrideStore()
    baseline = definition.default_factory()
    override = store.get(definition.id)
    active = str(override.get("content", baseline)) if override else baseline
    return {
        "id": definition.id,
        "task": definition.task,
        "title": definition.title,
        "slot": definition.slot,
        "priority": definition.priority,
        "description": definition.description,
        "editable": definition.editable,
        "variables": list(definition.variables),
        "baseline": baseline,
        "active": active,
        "source": "override" if override else "builtin",
        "overrideVersion": int(override.get("version", 0)) if override else None,
        "estimatedTokens": _estimate_tokens(active),
    }


@dataclass(frozen=True)
class ComposedPrompt:
    text: str
    manifest: list[dict]


def compose_prompt(
    task: str,
    variables: Mapping[str, object],
    *,
    include: set[str] | None = None,
    runtime_parts: list[tuple[str, str, str]] | None = None,
    store: PromptOverrideStore | None = None,
    baselines: Mapping[str, str] | None = None,
) -> ComposedPrompt:
    store = store or PromptOverrideStore()
    parts: list[tuple[int, str, str, str, int | None]] = []
    for definition in SLICES:
        if definition.task != task or (include is not None and definition.id not in include):
            continue
        view = slice_view(definition, store)
        if baselines and definition.id in baselines and view["source"] == "builtin":
            view["active"] = str(baselines[definition.id])
        if not view["active"]:
            continue
        rendered = view["active"]
        for name in definition.variables:
            rendered = rendered.replace("{" + name + "}", str(variables.get(name, "")))
        parts.append((definition.priority, definition.id, rendered, view["source"], view["overrideVersion"]))
    for index, (part_id, content, reason) in enumerate(runtime_parts or [], start=1):
        if content:
            parts.append((900 + index, part_id, content, reason, None))
    parts.sort(key=lambda item: (item[0], item[1]))
    manifest = [
        {
            "sliceId": item[1], "source": item[3], "overrideVersion": item[4],
            "estimatedTokens": _estimate_tokens(item[2]),
            "contentHash": hashlib.sha256(item[2].encode("utf-8")).hexdigest()[:16],
        }
        for item in parts
    ]
    return ComposedPrompt("\n\n".join(item[2] for item in parts), manifest)


def list_slices(store: PromptOverrideStore | None = None) -> list[dict]:
    return [slice_view(item, store) for item in SLICES]
