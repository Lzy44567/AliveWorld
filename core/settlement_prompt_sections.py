"""Lossless boundaries for the legacy all-in-one settlement system prompt."""

from __future__ import annotations

from dataclasses import dataclass


STATE_MARKERS = (
    "【状态与系统规则】",
    "【极其严格的状态与系统规则】：",
)
CONTRACT_MARKERS = (
    "【严格 JSON 格式】",
    "【强制JSON格式】：",
)


@dataclass(frozen=True)
class SettlementPromptSections:
    core: str
    state_guidance: str
    state_contract: str
    split: bool

    def compose(self) -> str:
        return "\n\n".join(
            item for item in (self.core, self.state_guidance, self.state_contract) if item
        )

    def as_baselines(self) -> dict[str, str]:
        return {
            "story.settlement.core": self.core,
            "story.state.guidance": self.state_guidance,
            "story.state.contract": self.state_contract,
        }


def _find_marker(text: str, markers: tuple[str, ...], start: int = 0) -> int:
    positions = [position for marker in markers if (position := text.find(marker, start)) >= 0]
    return min(positions, default=-1)


def split_settlement_prompt(prompt: object) -> SettlementPromptSections:
    """Split only when both canonical blank-line boundaries are lossless.

    Unknown third-party layouts remain a single core slice. Guessing at a
    boundary could duplicate or silently discard a developer's prompt.
    """
    text = str(prompt or "")
    state_start = _find_marker(text, STATE_MARKERS)
    contract_start = _find_marker(text, CONTRACT_MARKERS, max(0, state_start))
    if (
        state_start < 2
        or contract_start <= state_start + 2
        or text[state_start - 2:state_start] != "\n\n"
        or text[contract_start - 2:contract_start] != "\n\n"
    ):
        return SettlementPromptSections(text, "", "", False)

    sections = SettlementPromptSections(
        core=text[:state_start - 2],
        state_guidance=text[state_start:contract_start - 2],
        state_contract=text[contract_start:],
        split=True,
    )
    if sections.compose() != text:
        return SettlementPromptSections(text, "", "", False)
    return sections


def settlement_prompt_baselines(prompt: object) -> dict[str, str]:
    return split_settlement_prompt(prompt).as_baselines()
