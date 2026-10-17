"""Deterministic OpenAI-compatible service for AliveWorld end-to-end tests."""

from __future__ import annotations

import json
import re
import time
import uuid
from threading import Lock
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
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
    stream: bool = False


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
    if "有限主动联系规划" in system:
        return "character.contact"
    if "character.reply" in system:
        return "character.reply"
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
    from tests.fakes.entity_reply import response as entity_response
    entity_reply = entity_response(kind, user)
    if entity_reply is not None:
        return entity_reply
    from tests.fakes.worldbook_reply import response as worldbook_response
    worldbook_reply = worldbook_response(kind, user)
    if worldbook_reply is not None:
        return worldbook_reply
    from tests.fakes.npc_reply import response as npc_response
    npc_reply = npc_response(kind, user)
    if npc_reply is not None:
        return npc_reply
    from tests.fakes.effect_reply import response as effect_response
    effect_reply = effect_response(kind, user)
    if effect_reply is not None:
        return effect_reply
    full = f"{system}\n{user}"
    if kind == "character.contact":
        maximum = json.loads(user)["max_contacts"]
        return {"contacts": [{"delay_seconds": index, "reply": {
            "messages": [{"local_id": "b0", "text": f"主动联系测试{index + 1}"}],
            "ledger_ops": [], "memory_annotations": []}}
            for index in range(min(maximum, 2))]}
    if kind == "character.reply":
        return _character_response(user)
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
                "fact_checks": [{
                    "fact": "自动验收玩家行动已被接受",
                    "compatible": True,
                    "reason": "固定候选保留已接受行动",
                }],
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
            "world_change_events": [],
            "action_suggestions": ["继续检查世界", "观察身边角色"],
            "preference_observations": [],
        }
    if kind == "overseer":
        if "中央炉务厅" in full:
            return {
                "undercurrent_events": [{
                    "entity": "中央炉务厅",
                    "action": "核对第七中继站的异常读数，并暂缓发出公开封锁令",
                    "status": "已建立内部核查，但尚未确认玩家持有何种证据",
                    "clues": ["一份带有限流签名的调度副本正送往第七站"],
                }],
                "new_entities": [],
                "new_influences": [{
                    "source_links": [{
                        "entity": "中央炉务厅", "life_link_strength": 0.2,
                        "on_source_death": "keep",
                    }],
                    "type": "persistent",
                    "summary": "炉务厅对第七中继站启动分级核查",
                    "condition": "玩家公开黑匣、进入受限炉线或调度核查人员抵达",
                    "effect": "正文体现核查带来的询问、权限变化或可追踪线索，不直接判定玩家有罪",
                    "consume_policy": {"mode": "never", "max_triggers": None},
                    "tags": ["自动验收", "制度影响"],
                }],
                "update_influences": [], "delete_influences": [],
                "update_entities": [], "delete_entities": [],
            }
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
        if "AW_REVIEW_BATCH" in user:
            return {"message": "三项草案等待审阅", "operations": [
                {"op": "add_entry", "entry": {"name": name, "content": f"{name}设定"}}
                for name in ["浮岛", "小店", "商人"]], "suggested_actions": []}
        return {
            "understanding": "自动验收工坊理解", "design_notes": ["按既有规则讨论"],
            "message": "本轮讨论已记录。自动验收工坊回复", "reply": "自动验收工坊回复",
            "operations": [], "suggestions": ["继续讨论"], "suggested_actions": ["继续讨论"],
        }
    return {"message": "AliveWorld 自动验收假模型响应"}


def _character_response(user: str) -> dict[str, Any] | str:
    """The character fixture never reuses story/workshop result contracts."""
    data = json.loads(user)
    contract_id = data.get('reply_contract_id', 'character.reply.v1')
    if contract_id == 'character.reply.v3':
        from tests.fakes.character_group_reply import response
        return response(data)
    if contract_id not in {'character.reply.v1', 'character.reply.v2'}:
        raise ValueError('Unknown test reply contract')
    context_id = data.get('context_contract_id', 'character.context.v1')
    if context_id not in {'character.context.v1', 'character.context.m3.v1', 'character.context.c3.v1'}:
        raise ValueError('Unknown test context contract')
    def output(ops, annotations=None):
        result = {'reply': reply, 'ledger_ops': ops}
        if contract_id == 'character.reply.v2':
            result['memory_annotations'] = annotations or []
        return result
    current = data.get("current_user_message", data.get("current_input", {}))
    content = current.get("content", "") if isinstance(current, dict) else str(current)
    mode = data.get("presentation_mode", "messenger")
    reply = f"自动验收角色回复（{mode}）：{content}"
    if '【角色世界话题】' in content:
        reply += ' 我们去钟楼看看吧。'
    if "【角色坏JSON】" in content:
        return json.dumps(output([]), ensure_ascii=False) + " trailing"
    if "【角色一次失败】" in content:
        with _lock:
            attempts = sum(record["kind"] == "character.reply" and
                           json.loads(record["user"]).get("current_user_message", {}).get("content") == content
                           for record in _requests)
        if attempts == 1:
            return json.dumps(output([]), ensure_ascii=False) + " trailing"
    operations = []
    if "【角色账本】" in content:
        participants = data["participants"]
        ai_id = next(p["instance_id"] for p in participants if p["controller"] == "ai")
        source = {"type": "player_statement", "message_ids": [current["message_id"]],
                  "evidence": [{"message_id": current["message_id"], "quote": content[:240]}]}
        operations = [
            {"op": "add", "kind": "knowledge", "content": content[:400] if '【记忆M1】' in content else "公开记录：收到用户陈述",
             "source": source, "visibility": {"audience_instance_ids": [p["instance_id"] for p in participants]}},
            {"op": "add", "kind": "belief", "content": "内部记录：暂时相信用户陈述",
             "source": {**source, "type": "model_inference"}, "visibility": {"audience_instance_ids": [ai_id]}},
        ]
    annotations = []
    if contract_id == 'character.reply.v2' and ('【记忆M2边界】' in content or '【记忆M2高光】' in content):
        participants = data['participants']
        user_id = next(p['instance_id'] for p in participants if p['controller'] == 'user')
        public_ids = [p['instance_id'] for p in participants]
        high = '【记忆M2高光】' in content
        source = {'type': 'dialogue_event' if high else 'player_statement', 'message_ids': [current['message_id']],
                  'evidence': [{'message_id': current['message_id'], 'quote': content[:240]}]}
        operation = {'op': 'add', 'kind': 'experience' if high else 'knowledge', 'content': content[:400],
                     'about_instance_id': user_id, 'source': source, 'visibility': {'audience_instance_ids': public_ids}}
        if '【M2修订】' in content:
            target = next((e for e in data.get('ledger', []) if e['kind'] == operation['kind'] and e.get('about_instance_id') == user_id), None)
            if target:
                operation.update(op='supersede', target_entry_id=target['entry_id'])
        operations = [operation]
        annotations = [{'op_index': 0, 'reason': 'relationship_turn' if high else 'explicit_boundary'}]
    if context_id == 'character.context.m3.v1' and '【记忆M3修订】' in content:
        user_id = next(p['instance_id'] for p in data['participants'] if p['controller'] == 'user')
        recalled = [m for m in data.get('recalled_sources', []) if m['speaker_instance_id'] == user_id]
        target = next((e for e in data.get('ledger', []) if e['kind'] == 'knowledge' and any(m['message_id'] in e['source']['message_ids'] for m in recalled)), None)
        if target:
            message = next(m for m in recalled if m['message_id'] in target['source']['message_ids'])
            reply += ' 收到旧声明的限定语：' + message['content'][:300]
            operations = [{'op': 'supersede', 'target_entry_id': target['entry_id'], 'kind': 'knowledge',
                'content': '收到旧声明的限定语：' + message['content'][:300], 'source': {'type': 'player_statement',
                    'message_ids': [message['message_id']], 'evidence': [{'message_id': message['message_id'], 'quote': message['content'][:240]}]},
                'visibility': target['visibility']}]
            if target.get('about_instance_id') is not None:
                operations[0]['about_instance_id'] = target['about_instance_id']
            annotations = []
    return output(operations, annotations)


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
        "stream": payload.stream,
        "markers": scan_prompt(f"{system}\n{user}"),
    }
    with _lock:
        _requests.append(record)
    content = _response_for(kind, system, user)
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    if payload.stream:
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        def chunks():
            # Delay individual upstream chunks so browser tests can observe
            # real previews before the final settlement and persistence.
            invalid_suffix = " trailing" if kind == "character.reply" and content.endswith(" trailing") else ""
            body = content[:-len(invalid_suffix)] if invalid_suffix else content
            pieces = [body[offset:offset + 12] for offset in range(0, len(body), 12)]
            if invalid_suffix:
                pieces.append(invalid_suffix)
            for index, piece in enumerate(pieces):
                if invalid_suffix and index == len(pieces) - 1:
                    # The complete visible reply must be observable before
                    # malformed trailing data proves it cannot be committed.
                    time.sleep(0.8)
                chunk = {
                    "id": response_id, "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": payload.model,
                    "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                }
                yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
                time.sleep((0.1 if "【角色慢流】" in user else 0.075)
                           if kind == "character.reply" else 0.025)
            if kind == "character.reply":
                # Hold upstream terminal completion briefly after all visible
                # text. Browser polling can then reliably observe unsaved
                # preview even for a short role reply; this is not UI fake typing.
                time.sleep(0.3)
            yield "data: " + json.dumps({
                "id": response_id, "object": "chat.completion.chunk",
                "created": int(time.time()), "model": payload.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")
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
