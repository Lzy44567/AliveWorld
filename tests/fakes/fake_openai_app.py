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


def _readiness_markers(full_prompt: str) -> list[str]:
    markers = []
    for needle, marker in (
        ("测试世界书", "世界书就绪"),
        ("测试角色卡", "角色卡就绪"),
        ("测试文风", "文风就绪"),
    ):
        if needle in full_prompt:
            markers.append(marker)
    return markers


def _response_for(kind: str, system: str, user: str) -> dict[str, Any] | str:
    full = f"{system}\n{user}"
    if kind == "reaction":
        influence_ids = list(dict.fromkeys(re.findall(r"influence_[A-Za-z0-9_-]+", full)))
        return {
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
        paragraphs = ["前端正文测试成功。", *_readiness_markers(full)]
        return {
            "story_text": "\n\n".join(paragraphs),
            "new_buffs": {},
            "remove_buffs": [],
            "dynamic_bars": {},
            "status_updates": {"身体": "自动验收正常"},
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
