"""Human-readable and structured local logging for AliveWorld."""

from __future__ import annotations

import glob
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from utils.runtime_paths import PATHS


LOG_DIR = str(PATHS.log_dir)
os.makedirs(LOG_DIR, exist_ok=True)
_current_log_file = None

CATEGORY_LABELS = {
    "story": "正文",
    "future": "未来推演",
    "undercurrent": "暗流",
    "worldbook": "世界书",
    "workshop": "工坊",
    "memory": "记忆",
    "preference": "偏好",
    "image": "生图",
    "system": "系统",
}


def _icon(level: int) -> str:
    if level >= logging.ERROR:
        return "❌"
    if level == logging.WARNING:
        return "⚠️"
    if level == logging.DEBUG:
        return "✅"
    return "ℹ️"


def classify_log(label: str = "", message: str = "", module: str = "") -> str:
    label_text = str(label or "").lower()
    label_rules = (
        ("image", ("生图", "comfyui", "image prompt")),
        ("workshop", ("工坊", "workshop")),
        ("memory", ("记忆", "压缩", "memory")),
        ("undercurrent", ("overseer", "暗流", "实体推演", "因果账本")),
        ("future", ("变数推演", "未来候选", "命运投掷")),
        ("story", ("剧情结算", "剧情重写", "正文", "settlement")),
        ("worldbook", ("世界书", "worldbook")),
        ("preference", ("偏好", "preference")),
    )
    for category, markers in label_rules:
        if any(marker in label_text for marker in markers):
            return category

    text = f"{message} {module}".lower()
    rules = (
        ("image", ("生图", "comfyui", "image prompt")),
        ("preference", ("偏好", "preference")),
        ("memory", ("记忆", "压缩", "memory")),
        ("workshop", ("工坊", "workshop")),
        ("worldbook", ("世界书", "worldbook")),
        ("undercurrent", ("overseer", "暗流", "实体推演", "因果账本")),
        ("future", ("变数推演", "未来候选", "命运投掷")),
        ("story", ("剧情结算", "剧情重写", "正文", "settlement")),
    )
    for category, markers in rules:
        if any(marker in text for marker in markers):
            return category
    return "system"


def redact_log_value(value):
    """Remove credentials and unnecessary local identity from structured details."""
    if isinstance(value, dict):
        return {
            str(key): ("***" if any(token in str(key).lower() for token in ("api_key", "authorization", "secret")) else redact_log_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    if not isinstance(value, str):
        return value
    text = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1***", value)
    text = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1***", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "sk-***", text)
    text = re.sub(r"(?i)C:\\Users\\[^\\\s]+", "%USERPROFILE%", text)
    return text


class CustomFormatter(logging.Formatter):
    def format(self, record):
        time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        module_name = getattr(record, "module_name", record.module)
        message = f"[{time_str}] {_icon(record.levelno)} [{module_name}] {record.getMessage()}"
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
        return message


class StructuredFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        label = str(getattr(record, "aw_task", "") or "")
        category = str(getattr(record, "aw_category", "") or classify_log(label, message, record.module))
        details = getattr(record, "aw_details", None)
        payload = {
            "id": str(getattr(record, "aw_event_id", "") or uuid4().hex[:12]),
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3],
            "level": record.levelname.lower(),
            "icon": _icon(record.levelno),
            "category": category if category in CATEGORY_LABELS else "system",
            "category_label": CATEGORY_LABELS.get(category, "系统"),
            "task": label or CATEGORY_LABELS.get(category, "系统"),
            "trace_id": str(getattr(record, "aw_trace_id", "") or ""),
            "story_id": str(getattr(record, "aw_story_id", "") or ""),
            "task_id": str(getattr(record, "aw_task_id", "") or ""),
            "phase": str(getattr(record, "aw_phase", "event") or "event"),
            "status": str(getattr(record, "aw_status", "error" if record.levelno >= logging.ERROR else "info")),
            "summary": redact_log_value(str(getattr(record, "aw_summary", "") or message.splitlines()[0])[:240]),
            "details": redact_log_value(details if details is not None else message),
        }
        if record.exc_info:
            payload["exception"] = redact_log_value(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def init_logger(log_filename):
    global _current_log_file
    _current_log_file = log_filename
    path = Path(log_filename).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("AliveWorld")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    human_handler = logging.FileHandler(path, encoding="utf-8")
    human_handler.setFormatter(CustomFormatter())
    logger.addHandler(human_handler)

    structured_handler = logging.FileHandler(path.with_suffix(".jsonl"), encoding="utf-8")
    structured_handler.setFormatter(StructuredFormatter())
    logger.addHandler(structured_handler)
    logger.propagate = False
    return logger


def get_logger():
    return logging.getLogger("AliveWorld")


def _latest_file(pattern: str, log_dir: str | Path = LOG_DIR) -> Path | None:
    files = [Path(item) for item in glob.glob(os.path.join(str(log_dir), pattern))]
    return max(files, key=os.path.getctime) if files else None


def read_logs_structured(*, category: str = "", trace_id: str = "", limit: int = 500, log_dir: str | Path = LOG_DIR):
    path = _latest_file("*.jsonl", log_dir)
    if not path:
        return []
    parsed = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if category and item.get("category") != category:
                continue
            if trace_id and item.get("trace_id") != trace_id:
                continue
            parsed.append(item)
        return parsed[-max(1, min(2000, int(limit or 500))):]
    except OSError:
        return []


def read_logs_parsed(*, category: str = "", trace_id: str = "", limit: int = 500):
    if _latest_file("*.jsonl"):
        return read_logs_structured(category=category, trace_id=trace_id, limit=limit)
    try:
        latest_log = _latest_file("*.log")
        if not latest_log:
            return [{"id":"empty", "time":"", "icon":"⚠️", "category":"system", "category_label":"系统", "task":"系统", "trace_id":"", "phase":"event", "status":"info", "summary":"暂无日志文件", "details":"暂无日志文件"}]
        parsed = []
        pattern = r"^\[(.*?)\]\s+(.*?)\s+\[(.*?)\]\s+(.*)$"
        for line in latest_log.read_text(encoding="utf-8").splitlines():
            match = re.match(pattern, line.strip())
            if match:
                message = match.group(4)
                legacy_category = classify_log(message=message, module=match.group(3))
                parsed.append({
                    "id": f"legacy-{len(parsed)}", "time": match.group(1), "icon": match.group(2),
                    "category": legacy_category,
                    "category_label": CATEGORY_LABELS.get(legacy_category, "系统"),
                    "task": match.group(3), "trace_id": "", "phase": "event", "status": "legacy",
                    "summary": message[:240], "details": message,
                })
            elif parsed:
                parsed[-1]["details"] += f"\n{line.rstrip()}"
        if category:
            parsed = [item for item in parsed if item["category"] == category]
        return parsed[-max(1, min(2000, int(limit or 500))):]
    except Exception as exc:
        return [{"id":"error", "time":"", "icon":"❌", "category":"system", "category_label":"系统", "task":"系统", "trace_id":"", "phase":"event", "status":"error", "summary":"日志解析失败", "details":f"日志解析失败: {exc}"}]
