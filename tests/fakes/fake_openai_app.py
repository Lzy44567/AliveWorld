"""Deterministic OpenAI-compatible service for AliveWorld end-to-end tests."""

from __future__ import annotations

import json
import re
import time
import uuid
from threading import Lock
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from tests.fakes.prompt_contract import next_story_index, scan_prompt, visible_readiness_lines


app = FastAPI(title="AliveWorld deterministic fake model")
_requests: list[dict[str, Any]] = []
_lock = Lock()


class ChatRequest(BaseModel):
    model: str = "fake-story"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    response_format: dict[str, Any] | None = None
    max_tokens: int | None = None


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _classify(system: str) -> str:
    if "近期未来推演器" in system:
        return "reaction"
    if "游戏地下城主" in system:
        return "settlement"
    if "Overseer" in system and "活跃暗流实体" in system:
        return "overseer"
    if "世界书" in system and ("捕获" in system or "候选" in system):
        return "worldbook_capture"
    if "记忆" in system and ("总结" in system or "压缩" in system):
        return "memory"
    if "偏好" in system and ("贝叶斯" in system or "证据" in system):
        return "preference"
    if "生图" in system or "图像提示词" in system:
        return "image_prompt"
    if "工坊" in system or "草稿" in system:
        return "workshop"
    return "unknown"


def _response_for(kind: str, system: str, user: str) -> dict[str, Any] | str:
    full = f"{system}\n{user}"
    if kind == "reaction":
        influence_ids = list(dict.fromkeys(re.findall(r"influence_[A-Za-z0-9_-]+", full)))
        return {
            "action_adjudication": {
                "accepted_facts": ["自动验收玩家行动已被接受"],
                "contested_outcomes": [],
                "rejected_claims": [],
            },
            "reactions": [{
                "id": 1,
                "description": "测试世界按既有事实继续运行",
                "eligible": True,
                "weight": 100,
                "basis": ["自动验收固定候选"],
            }],
            "influence_checks": [
                {"id": item, "condition_met": False, "reason": "自动验收默认不触发"}
                for item in influence_ids
            ],
        }
    if kind == "settlement":
        story_index = next_story_index(full)
        paragraphs = [
            "前端正文测试成功。",
            f"自动测试正文{story_index}",
            *visible_readiness_lines(full),
        ]
        return {
            "story_text": "\n\n".join(paragraphs),
            "new_buffs": {},
            "remove_buffs": [],
            "dynamic_bars": {
                "自动验收进度": {
                    "current": min(story_index, 5), "max": 5, "color": "cyan",
                },
            },
            "status_updates": {
                "身体": "自动验收正常",
                "自动验收阶段": f"第{story_index}回合",
                "当前时间": f"自动纪元第{story_index}回合",
            },
            "npc_states": {},
            "status_deletions": [],
            "resolved_influences": [],
            "worldbook_capture_needed": False,
            "action_suggestions": ["继续检查世界", "观察身边角色"],
            "preference_observations": [],
        }
    if kind == "overseer":
        return {
            "undercurrent_events": [], "new_entities": [], "new_influences": [],
            "update_influences": [], "delete_influences": [],
            "update_entities": [], "delete_entities": [],
        }
    if kind == "worldbook_capture":
        return {"entries": [], "skipped": ["自动验收不新增设定"]}
    if kind == "memory":
        return {"summary": "自动验收记忆摘要", "important_memories": [], "core_memories": []}
    if kind == "preference":
        return {"hypotheses": [], "coverage_gaps": []}
    if kind == "image_prompt":
        return {"positive": "test scene, one character", "negative": "low quality"}
    if kind == "workshop":
        return {"reply": "自动验收工坊回复", "operations": [], "suggestions": ["继续讨论"]}
    return {"message": "AliveWorld 自动验收假模型响应"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "owned_by": "aliveworld-tests"}
            for name in (
                "fake-story", "fake-overseer", "fake-workshop", "fake-memory",
                "fake-preference", "fake-image-prompt",
            )
        ],
    }


@app.post("/v1/chat/completions")
def chat(payload: ChatRequest):
    system = _message_text(payload.messages[0]) if payload.messages else ""
    user = "\n".join(_message_text(item) for item in payload.messages[1:])
    kind = _classify(system)
    record = {
        "id": str(uuid.uuid4()), "time": time.time(), "kind": kind,
        "model": payload.model, "system": system, "user": user,
        "markers": scan_prompt(f"{system}\n{user}"),
    }
    with _lock:
        _requests.append(record)
    content = _response_for(kind, system, user)
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
        "created": int(time.time()), "model": payload.model,
        "choices": [{
            "index": 0, "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
    }


@app.get("/__test__/requests")
def recorded_requests():
    with _lock:
        return {"requests": list(_requests)}


@app.delete("/__test__/requests")
def clear_requests():
    with _lock:
        _requests.clear()
    return {"status": "cleared"}


@app.get("/__test__/coverage")
def prompt_coverage():
    """Summarize which markers reached which task, without exposing player data."""

    with _lock:
        records = list(_requests)
    tasks: dict[str, int] = {}
    markers: dict[str, dict[str, int]] = {}
    for record in records:
        kind = str(record.get("kind") or "unknown")
        tasks[kind] = tasks.get(kind, 0) + 1
        for marker in record.get("markers") or []:
            by_task = markers.setdefault(str(marker), {})
            by_task[kind] = by_task.get(kind, 0) + 1
    return {"request_count": len(records), "tasks": tasks, "markers": markers}
