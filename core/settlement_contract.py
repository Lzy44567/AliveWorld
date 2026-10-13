"""Deterministic validation for story settlement model output.

The model proposes narrative and state operations.  This module owns the
machine-checkable contract before any ledger, history, or state mutation is
committed.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from utils.sys_logger import get_logger
from core.world_change_events import validate_world_change_events
from core.npc_identity import NpcIdentityError, validate_identity_updates


log = get_logger()

MAX_COLLECTION_ITEMS = 100
MAX_NAME_LENGTH = 120
MAX_TEXT_LENGTH = 20_000
STATE_GROUPS = ("properties", "bars", "buffs", "npcs")


class SettlementContractError(ValueError):
    """The model response cannot be applied without guessing its meaning."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.reason = message
        super().__init__(f"{path}: {message}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SettlementContractError(path, "必须是对象")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise SettlementContractError(path, f"最多允许 {MAX_COLLECTION_ITEMS} 项")
    return value


def _sequence(value: Any, path: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SettlementContractError(path, "必须是数组")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise SettlementContractError(path, f"最多允许 {MAX_COLLECTION_ITEMS} 项")
    return value


def _name(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SettlementContractError(path, "必须是非空文本")
    text = value.strip()
    if len(text) > MAX_NAME_LENGTH:
        raise SettlementContractError(path, f"长度不能超过 {MAX_NAME_LENGTH}")
    return text


def _text(value: Any, path: str, *, required: bool = False, maximum: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise SettlementContractError(path, "必须是文本")
    text = value.strip()
    if required and not text:
        raise SettlementContractError(path, "不能为空")
    if len(text) > maximum:
        raise SettlementContractError(path, f"长度不能超过 {maximum}")
    return text


def _number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SettlementContractError(path, "必须是有限数值")
    return value


def _bounded_value(value: Any, path: str, *, depth: int = 0) -> Any:
    if depth > 3:
        raise SettlementContractError(path, "嵌套层级过深")
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            raise SettlementContractError(path, "不能包含非有限数值")
        if isinstance(value, str) and len(value) > 4000:
            raise SettlementContractError(path, "文本过长")
        return copy.deepcopy(value)
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise SettlementContractError(path, "对象项目过多")
        return {
            _name(key, f"{path}.key"): _bounded_value(item, f"{path}.{key}", depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise SettlementContractError(path, "数组项目过多")
        return [_bounded_value(item, f"{path}[{index}]", depth=depth + 1) for index, item in enumerate(value)]
    raise SettlementContractError(path, "包含不支持的数据类型")


def _unique_names(value: Any, path: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(_sequence(value, path)):
        name = _name(item, f"{path}[{index}]")
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _validate_bars(value: Any, current_state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    current_bars = current_state.get("bars", {}) if isinstance(current_state, Mapping) else {}
    current_bars = current_bars if isinstance(current_bars, Mapping) else {}
    result: dict[str, dict[str, Any]] = {}
    for raw_name, raw_update in _mapping(value, "dynamic_bars").items():
        name = _name(raw_name, "dynamic_bars.key")
        update = _mapping(raw_update, f"dynamic_bars.{name}")
        allowed = {"current", "change", "max", "color"}
        unknown = set(update) - allowed
        if unknown:
            raise SettlementContractError(f"dynamic_bars.{name}", f"包含未知字段 {sorted(unknown)[0]}")
        clean: dict[str, Any] = {}
        for field in ("current", "change", "max"):
            if field in update:
                clean[field] = _number(update[field], f"dynamic_bars.{name}.{field}")
        if "max" in clean and clean["max"] <= 0:
            raise SettlementContractError(f"dynamic_bars.{name}.max", "必须大于 0")
        if "color" in update:
            clean["color"] = _text(update["color"], f"dynamic_bars.{name}.color", required=True, maximum=40)
        exists = name in current_bars
        if exists and "current" in clean and "change" in clean:
            raise SettlementContractError(f"dynamic_bars.{name}", "已有进度条只能提交 current 或 change 之一")
        if not exists:
            if "change" in clean:
                raise SettlementContractError(f"dynamic_bars.{name}", "新进度条不能使用 change")
            if "current" not in clean or "max" not in clean:
                raise SettlementContractError(f"dynamic_bars.{name}", "新进度条必须同时提供 current 和 max")
        result[name] = clean
    return result


def _validate_deletions(
    value: Any,
    current_state: Mapping[str, Any],
    additions: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    deletions = _unique_names(value, "status_deletions")
    for name in deletions:
        matches = []
        for group in STATE_GROUPS:
            existing = current_state.get(group, {}) if isinstance(current_state, Mapping) else {}
            added = additions.get(group, {})
            if (isinstance(existing, Mapping) and name in existing) or name in added:
                matches.append(group)
        if len(matches) > 1:
            raise SettlementContractError(
                "status_deletions",
                f"{name} 同时存在于 {', '.join(matches)}，名称删除存在歧义",
            )
    return deletions


def validate_settlement(
    payload: Any,
    *,
    current_state: Mapping[str, Any] | None = None,
    triggered_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Return a safe normalized copy or raise ``SettlementContractError``."""

    if not isinstance(payload, dict):
        raise SettlementContractError("settlement", "必须是 JSON 对象")
    state = current_state if isinstance(current_state, Mapping) else {}
    result = copy.deepcopy(payload)
    result["story_text"] = _text(payload.get("story_text"), "story_text", required=True)

    new_buffs: dict[str, dict[str, Any]] = {}
    for raw_name, raw_buff in _mapping(payload.get("new_buffs"), "new_buffs").items():
        name = _name(raw_name, "new_buffs.key")
        buff = _bounded_value(_mapping(raw_buff, f"new_buffs.{name}"), f"new_buffs.{name}")
        duration = buff.get("duration")
        if duration is not None and (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration < -1
        ):
            raise SettlementContractError(
                f"new_buffs.{name}.duration", "必须是 -1 或非负整数",
            )
        for field, field_value in buff.items():
            if field.endswith("_per_turn"):
                _number(field_value, f"new_buffs.{name}.{field}")
        if 'tick_seconds' in buff:
            if type(buff['tick_seconds']) is not int or not 0 < buff['tick_seconds'] <= 31536000:
                raise SettlementContractError(f'new_buffs.{name}.tick_seconds', '必须为1至31536000之间的整数秒周期')
            buff['tick_elapsed'] = 0
        else:
            buff.pop('tick_elapsed', None)
        new_buffs[name] = buff
    result["new_buffs"] = new_buffs
    result["remove_buffs"] = _unique_names(payload.get("remove_buffs"), "remove_buffs")
    result["dynamic_bars"] = _validate_bars(payload.get("dynamic_bars"), state)

    status_updates: dict[str, Any] = {}
    for raw_name, raw_value in _mapping(payload.get("status_updates"), "status_updates").items():
        name = _name(raw_name, "status_updates.key")
        status_updates[name] = _bounded_value(raw_value, f"status_updates.{name}")
    result["status_updates"] = status_updates

    npc_states: dict[str, Any] = {}
    for raw_name, raw_value in _mapping(payload.get("npc_states"), "npc_states").items():
        name = _name(raw_name, "npc_states.key")
        npc_states[name] = _bounded_value(raw_value, f"npc_states.{name}")
    result["npc_states"] = npc_states
    try:
        result['npc_identity_updates'] = validate_identity_updates(payload.get('npc_identity_updates'))
    except NpcIdentityError as exc:
        raise SettlementContractError('npc_identity_updates', str(exc)) from exc
    result["status_deletions"] = _validate_deletions(
        payload.get("status_deletions"),
        state,
        {
            "properties": status_updates,
            "bars": result["dynamic_bars"],
            "buffs": new_buffs,
            "npcs": npc_states,
        },
    )

    expected = {str(item) for item in (triggered_ids or set()) if str(item)}
    identity_names = {item[key] for item in result['npc_identity_updates']
                      for key in ('name', 'previous_name') if key in item}
    if identity_names.intersection(result['status_deletions']):
        raise SettlementContractError('npc_identity_updates', '身份更新不要同时删除人物，请使用present=false')
    resolved: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(_sequence(payload.get("resolved_influences"), "resolved_influences")):
        item = _mapping(raw, f"resolved_influences[{index}]")
        influence_id = _name(item.get("id"), f"resolved_influences[{index}].id")
        if influence_id not in expected:
            log.warning("忽略正文越权报告的暗流影响: %s", influence_id)
            continue
        if influence_id in seen:
            log.warning("忽略正文重复报告的暗流影响: %s", influence_id)
            continue
        seen.add(influence_id)
        resolved.append({
            "id": influence_id,
            "result": _text(item.get("result"), f"resolved_influences[{index}].result", required=True, maximum=1000),
        })
    missing = sorted(expected - seen)
    if missing:
        raise SettlementContractError("resolved_influences", f"缺少必须兑现的影响 {missing[0]}")
    result["resolved_influences"] = resolved
    if "world_change_events" in payload:
        try:
            result["world_change_events"] = validate_world_change_events(payload["world_change_events"])
        except ValueError as exc:
            raise SettlementContractError("world_change_events", str(exc)) from exc
    if "worldbook_capture_needed" in payload:
        if not isinstance(payload["worldbook_capture_needed"], bool):
            raise SettlementContractError("worldbook_capture_needed", "必须是布尔值")
        result["worldbook_capture_needed"] = payload["worldbook_capture_needed"]
    return result
