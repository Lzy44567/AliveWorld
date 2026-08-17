"""Build feedback previews and in-memory diagnostic archives from whitelisted data."""

from __future__ import annotations

import io
import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from typing import Iterable

from core.feedback.models import ALLOWED_CATEGORIES, FeedbackDraft
from core.feedback.redaction import contains_suspected_secret, redact
from utils.runtime_paths import PATHS
from utils.sys_logger import read_logs_parsed
from utils.version import APP_VERSION


def _recent_events(limit: int = 120) -> list[dict]:
    return [redact(item) for item in read_logs_parsed(limit=limit) if isinstance(item, dict)]


def _safe_event_summary(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "time": str(item.get("time") or ""),
        "level": str(item.get("level") or ""),
        "category": str(item.get("category") or "system"),
        "category_label": str(item.get("category_label") or "系统"),
        "task": str(item.get("task") or ""),
        "trace_id": str(item.get("trace_id") or ""),
        "phase": str(item.get("phase") or "event"),
        "status": str(item.get("status") or ""),
        "summary": str(item.get("summary") or "")[:240],
    }


def environment_snapshot() -> dict:
    return {
        "aliveworld_version": APP_VERSION,
        "run_mode": "portable" if PATHS.frozen else "source",
        "packaged": PATHS.frozen,
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_runtime": platform.python_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def feedback_context() -> dict:
    events = _recent_events()
    errors = [item for item in events if str(item.get("level") or "").lower() in {"error", "critical"} or str(item.get("status") or "").lower() in {"error", "failed"}]
    candidates = errors[-20:] if errors else events[-10:]
    return {"environment": environment_snapshot(), "recent_events": [_safe_event_summary(item) for item in reversed(candidates)]}


def _selected_events(ids: Iterable[str]) -> list[dict]:
    wanted = {str(item) for item in ids if item}
    if not wanted:
        return []
    return [item for item in _recent_events(limit=2000) if str(item.get("id") or "") in wanted]


def _markdown(draft: FeedbackDraft, environment: dict, logs: list[dict]) -> str:
    label = ALLOWED_CATEGORIES[draft.category]
    lines = [
        f"# {draft.title or 'AliveWorld 玩家反馈'}",
        "",
        f"- 分类：{label}",
        f"- AliveWorld：{environment['aliveworld_version']}",
        f"- 运行方式：{environment['run_mode']}",
        f"- 系统：{environment['os']} {environment['os_release']} ({environment['architecture']})",
    ]
    if draft.trace_id:
        lines.append(f"- Trace ID：`{draft.trace_id}`")
    lines.extend(["", "## 实际表现", "", draft.actual or "（未填写）", "", "## 期望表现", "", draft.expected or "（未填写）"])
    if draft.steps:
        lines.extend(["", "## 复现步骤", "", draft.steps])
    if logs:
        lines.extend(["", "## 玩家主动选择的日志", ""])
        for item in logs:
            lines.append(f"- `{item.get('time', '')}` [{item.get('category_label', '系统')}] trace `{item.get('trace_id', '') or '-'}`：{item.get('summary', '')}")
    lines.extend(["", "> 该摘要由 AliveWorld 在本机生成；发送前请再次检查是否含私人故事内容。"])
    return "\n".join(lines)


def build_feedback_preview(draft: FeedbackDraft) -> dict:
    normalized = draft.normalized()
    environment = redact(environment_snapshot())
    selected = redact(_selected_events(normalized.selected_log_ids))
    markdown = redact(_markdown(normalized, environment, selected))
    payload = {
        "markdown": markdown,
        "environment": environment,
        "selected_logs": selected,
        "selected_log_count": len(selected),
    }
    payload["blocked_by_secret_scan"] = contains_suspected_secret(payload)
    return payload


def build_diagnostic_zip(draft: FeedbackDraft) -> tuple[bytes, str]:
    preview = build_feedback_preview(draft)
    if preview["blocked_by_secret_scan"]:
        raise ValueError("诊断内容仍疑似包含密钥，请删除或遮罩后重试。")
    manifest = {
        "format": "aliveworld-diagnostic-v1",
        "contains_story_content": bool(preview["selected_logs"]),
        "files": ["feedback.md", "environment.json"] + (["logs.jsonl"] if preview["selected_logs"] else []),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("feedback.md", preview["markdown"])
        archive.writestr("environment.json", json.dumps(preview["environment"], ensure_ascii=False, indent=2))
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if preview["selected_logs"]:
            archive.writestr("logs.jsonl", "\n".join(json.dumps(item, ensure_ascii=False) for item in preview["selected_logs"]))
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return buffer.getvalue(), f"AliveWorld-diagnostic-{APP_VERSION}-{timestamp}.zip"
