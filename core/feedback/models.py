"""Feedback domain models independent from FastAPI and Vue."""

from __future__ import annotations

from dataclasses import dataclass, field


ALLOWED_CATEGORIES = {
    "bug": "功能错误",
    "ui": "界面与交互",
    "model": "模型与网络",
    "image": "生图",
    "suggestion": "内容建议",
    "other": "其他",
}


@dataclass(slots=True)
class FeedbackDraft:
    category: str = "bug"
    title: str = ""
    actual: str = ""
    expected: str = ""
    steps: str = ""
    trace_id: str = ""
    selected_log_ids: list[str] = field(default_factory=list)

    def normalized(self) -> "FeedbackDraft":
        category = self.category if self.category in ALLOWED_CATEGORIES else "other"
        return FeedbackDraft(
            category=category,
            title=self.title.strip()[:160],
            actual=self.actual.strip()[:8000],
            expected=self.expected.strip()[:8000],
            steps=self.steps.strip()[:8000],
            trace_id=self.trace_id.strip()[:80],
            selected_log_ids=[str(item)[:80] for item in self.selected_log_ids[:50]],
        )
