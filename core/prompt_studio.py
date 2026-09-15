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
from typing import Callable, Mapping, Sequence

from core.action_suggestions import action_suggestion_instruction
from core.player_agency import player_agency_instruction
from core.prompts import load_system_prompts
from core.prompt_variables import normalize_values, render_variable, require_variable, resolve_variable
from core.settlement_prompt_sections import split_settlement_prompt
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
    layer: str = "feature"
    cache_class: str = "static"
    required: bool = False
    required_variables: tuple[str, ...] | None = None


@dataclass(frozen=True)
class RuntimePromptPart:
    id: str
    content: str
    source: str = "runtime"
    layer: str = "feature"
    slot: str = "system"
    cache_class: str = "turn"


def _yaml_prompt(key: str) -> Callable[[], str]:
    return lambda: str(load_system_prompts().get(key, "") or "")


def _settlement_section(name: str) -> Callable[[], str]:
    return lambda: getattr(
        split_settlement_prompt(load_system_prompts().get("settlement_prompt", "")), name
    )


SLICES: tuple[PromptSlice, ...] = (
    PromptSlice("story.future.core", "story.future", "近期未来核心", "system", 100,
                "生成候选未来、行动裁定与暗流条件判断。", True,
                ("context.world", "context.player_character"), _yaml_prompt("reaction_prompt"),
                "engine", "static", True, ()),
    PromptSlice("story.future.player_agency", "story.future", "玩家行动权", "system", 200,
                "区分玩家可确定事实与需要世界裁定的外部结果。", True, (),
                lambda: player_agency_instruction(), "engine", "static", True),
    PromptSlice("story.future.continuity", "story.future", "剧情连续性", "system", 300,
                "约束信息通道、客观事实与外部介入。", True, (), continuity_instruction),
    PromptSlice("story.settlement.core", "story.settlement", "正文结算核心", "system", 100,
                "续写正文并返回状态、世界书捕获等结构字段。", True,
                ("context.style", "context.world", "context.player_character"),
                _settlement_section("core"), "engine", "static", True, ()),
    PromptSlice("story.state.guidance", "story.settlement", "状态与系统指导", "system", 120,
                "说明状态条、NPC、Buff、删除语义及与正文协作的更新时机。", True, (),
                _settlement_section("state_guidance"), "feature", "static", True),
    PromptSlice("story.state.contract", "story.settlement", "状态与结算输出契约", "system", 140,
                "后端解析所依赖的严格 JSON 字段；首版只读，避免破坏存档事务。", False, (),
                _settlement_section("state_contract"), "engine", "static", True),
    PromptSlice("story.settlement.player_agency", "story.settlement", "玩家行动权", "system", 200,
                "禁止正文替玩家新增重大决定。", True, (),
                lambda: player_agency_instruction(require_output=False), "engine", "static", True),
    PromptSlice("story.settlement.continuity", "story.settlement", "剧情连续性", "system", 300,
                "保持事实、信息通道和场景对象连续。", True, (), continuity_instruction),
    PromptSlice("story.settlement.length", "story.settlement", "正文篇幅", "system", 500,
                "根据单局设置动态生成篇幅要求。", False, ("settings.story_length",),
                lambda: story_length_instruction(500), "feature", "configuration"),
    PromptSlice("story.settlement.suggestions", "story.settlement", "快捷行动", "system", 800,
                "仅在启用快捷行动按钮时动态加入。", False, ("settings.action_suggestions",),
                lambda: action_suggestion_instruction(True), "feature", "configuration"),
    PromptSlice("world.capture.runtime", "world.capture", "世界观设定捕获", "system", 100,
                "当前由世界书捕获模块维护；尚未迁移到可编辑注册表。", False, (), lambda: ""),
    PromptSlice("workshop.runtime", "workshop", "工坊协作", "system", 100,
                "当前由各工坊模块维护；尚未迁移到可编辑注册表。", False, (), lambda: ""),
)

SLICE_BY_ID = {item.id: item for item in SLICES}
_CANONICAL_VARIABLE_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_.]*)\s*\}\}")
_LEGACY_VARIABLE_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


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
        except (OSError, json.JSONDecodeError):
            return {"overrides": {}}
        data = value if isinstance(value, dict) else {"overrides": {}}
        if self._migrate_legacy_settlement_override(data):
            # A migration write failure must be visible; silently returning an
            # empty store would temporarily discard the developer's override.
            _atomic_json(self.path, data)
        return data

    @staticmethod
    def _migrate_legacy_settlement_override(data: dict) -> bool:
        overrides = data.get("overrides")
        if not isinstance(overrides, dict):
            return False
        record = overrides.get("story.settlement.core")
        if not isinstance(record, dict) or not isinstance(record.get("content"), str):
            return False
        sections = split_settlement_prompt(record["content"])
        if not sections.split:
            return False

        try:
            version = max(1, int(record.get("version", 1)))
        except (TypeError, ValueError):
            version = 1
        migration = {"migratedFrom": "story.settlement.core@legacy-full"}
        overrides["story.settlement.core"] = {
            **record, "content": sections.core, **migration,
        }
        overrides.setdefault("story.state.guidance", {
            "version": version, "content": sections.state_guidance, **migration,
        })
        overrides.setdefault("story.state.contract", {
            "version": version, "content": sections.state_contract, **migration,
        })
        return True

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
    found: set[str] = set()
    for name in _CANONICAL_VARIABLE_RE.findall(content):
        definition = resolve_variable(name)
        found.add(definition.id if definition else name)
    for name in _LEGACY_VARIABLE_RE.findall(content):
        definition = resolve_variable(name)
        found.add(definition.id if definition else name)
    return found


def validate_template(definition: PromptSlice, content: str) -> None:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("提示词不能为空")
    actual = template_variables(content)
    allowed = set(definition.variables)
    unknown = actual - allowed
    required = set(
        definition.variables if definition.required_variables is None else definition.required_variables
    )
    missing = required - actual
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
        "variableDetails": [require_variable(item).view() for item in definition.variables],
        "layer": definition.layer,
        "cacheClass": definition.cache_class,
        "required": definition.required,
        "requiredVariables": list(
            definition.variables if definition.required_variables is None else definition.required_variables
        ),
        "baseline": baseline,
        "active": active,
        "source": "override" if override else "builtin",
        "overrideVersion": int(override.get("version", 0)) if override else None,
        "estimatedTokens": _estimate_tokens(active),
    }


def active_slice_variables(
    slice_id: str,
    *,
    store: PromptOverrideStore | None = None,
    baselines: Mapping[str, str] | None = None,
) -> set[str]:
    """Inspect variables embedded by the active template before rendering."""
    definition = require_slice(slice_id)
    store = store or PromptOverrideStore()
    view = slice_view(definition, store)
    template = view["active"]
    if baselines and slice_id in baselines and view["source"] == "builtin":
        template = str(baselines[slice_id])
    return template_variables(template)


@dataclass(frozen=True)
class ComposedPrompt:
    text: str
    manifest: list[dict]


@dataclass(frozen=True)
class RequestMessagePart:
    """One observable part of a model-bound message.

    ``separator`` is part of the wire text before ``content``. Keeping it here
    lets a builder expose useful provenance without changing a legacy prompt by
    even one newline.
    """

    id: str
    content: str
    separator: str = ""
    cache_class: str = "turn"


@dataclass(frozen=True)
class ModelRequestPlan:
    system_prompt: str
    user_prompt: str
    prompt_manifest: list[dict]
    temperature: float
    max_tokens: int | None
    trace_label: str
    mode: str
    contract_id: str


def plan_model_request(
    system: ComposedPrompt,
    user_parts: Sequence[RequestMessagePart],
    *,
    temperature: float,
    max_tokens: int | None,
    trace_label: str,
    mode: str,
    contract_id: str,
) -> ModelRequestPlan:
    """Create an immutable request plan while preserving exact message text."""
    user_prompt = ""
    manifest = [dict(item, messageRole="system") for item in system.manifest]
    for part in user_parts:
        if not part.content:
            continue
        user_prompt += part.separator + part.content
        manifest.append({
            "sliceId": part.id,
            "source": "runtime",
            "overrideVersion": None,
            "layer": "runtime",
            "slot": "user",
            "messageRole": "user",
            "cacheClass": part.cache_class,
            "estimatedTokens": _estimate_tokens(part.separator + part.content),
            "contentHash": hashlib.sha256(part.content.encode("utf-8")).hexdigest()[:16],
            "prefixHash": hashlib.sha256(
                (system.text + "\0" + user_prompt).encode("utf-8")
            ).hexdigest()[:16],
        })
    return ModelRequestPlan(
        system_prompt=system.text,
        user_prompt=user_prompt,
        prompt_manifest=manifest,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_label=trace_label,
        mode=mode,
        contract_id=contract_id,
    )


def compose_prompt(
    task: str,
    variables: Mapping[str, object],
    *,
    include: set[str] | None = None,
    runtime_parts: Sequence[tuple[str, str, str] | RuntimePromptPart] | None = None,
    store: PromptOverrideStore | None = None,
    baselines: Mapping[str, str] | None = None,
) -> ComposedPrompt:
    store = store or PromptOverrideStore()
    normalized_variables = normalize_values(dict(variables))
    parts: list[tuple[int, str, str, str, int | None, str, str, str]] = []
    for definition in SLICES:
        if definition.task != task or (include is not None and definition.id not in include):
            continue
        view = slice_view(definition, store)
        if baselines and definition.id in baselines and view["source"] == "builtin":
            view["active"] = str(baselines[definition.id])
        if not view["active"]:
            continue
        rendered = view["active"]
        for variable_id in definition.variables:
            rendered = render_variable(
                rendered, require_variable(variable_id), normalized_variables.get(variable_id, "")
            )
        parts.append((
            definition.priority, definition.id, rendered, view["source"], view["overrideVersion"],
            definition.layer, definition.slot, definition.cache_class,
        ))
    for index, raw_part in enumerate(runtime_parts or [], start=1):
        part = (
            raw_part if isinstance(raw_part, RuntimePromptPart)
            else RuntimePromptPart(raw_part[0], raw_part[1], raw_part[2], "runtime", "system", "turn")
        )
        if part.content:
            parts.append((
                900 + index, part.id, part.content, part.source, None,
                part.layer, part.slot, part.cache_class,
            ))
    parts.sort(key=lambda item: (item[0], item[1]))
    manifest = []
    prefix_parts: list[str] = []
    for item in parts:
        prefix_parts.append(item[2])
        manifest.append({
            "sliceId": item[1], "source": item[3], "overrideVersion": item[4],
            "layer": item[5], "slot": item[6], "cacheClass": item[7],
            "estimatedTokens": _estimate_tokens(item[2]),
            "contentHash": hashlib.sha256(item[2].encode("utf-8")).hexdigest()[:16],
            "prefixHash": hashlib.sha256("\n\n".join(prefix_parts).encode("utf-8")).hexdigest()[:16],
        })
    return ComposedPrompt("\n\n".join(item[2] for item in parts), manifest)


def list_slices(store: PromptOverrideStore | None = None) -> list[dict]:
    return [slice_view(item, store) for item in SLICES]
