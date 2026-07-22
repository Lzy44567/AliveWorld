"""Low-frequency preference analyst and deterministic Bayesian updates."""

from __future__ import annotations

import json
import threading
from typing import Any

from core.ai_engine import robust_json_parse
from utils.sys_logger import get_logger


log = get_logger()
MIN_EVIDENCE_BATCH = 6
LIKELIHOOD_RATIOS = {
    ("support", "weak"): 1.25,
    ("support", "moderate"): 2.0,
    ("support", "strong"): 4.0,
    ("against", "weak"): 0.8,
    ("against", "moderate"): 0.5,
    ("against", "strong"): 0.25,
    ("neutral", "weak"): 1.0,
    ("neutral", "moderate"): 1.0,
    ("neutral", "strong"): 1.0,
}


ANALYSIS_PROMPT = """你是谨慎的玩家偏好研究员。你读取的是行为证据，不是已经成立的心理结论。

目标是提出可以被未来证据证伪或增强的偏好假设。不要把一次选择直接等同于偏好；重掷、撤回、重新生成等行为可能来自审美、角色扮演、战术、求胜、好奇或随机结果不利。

规则：
1. 对同一证据提出多个合理的竞争解释。假设可以同时成立，不要求概率总和为100%。
2. 你不可能穷尽真实原因。coverage_note 必须说明本轮解释覆盖的局限，missing_possibilities 保留尚未想到或需要玩家说明的方向。
3. 只使用给出的 evidence_id。不得虚构玩家行为、跨故事事实或心理诊断。
4. strength 只能是 weak、moderate、strong；direction 只能是 support、against、neutral。Python 会把词汇映射为固定似然比并计算后验，你不得输出概率或自行宣布结论已确定。
5. weak：证据有很多常见替代解释；moderate：在上下文中明显支持但仍非唯一解释；strong：玩家跨情景反复表现，或证据几乎直接指向该动机。单次重掷/撤回通常只能是 weak。
6. 敏感内容只能在输入中确实存在敏感证据时提出，并标记 sensitive=true。
7. 优先更新现有 target_id；只有确实出现新解释时新建假设。描述玩家希望获得的体验或心理回报，而不是重复动作表面。

严格输出 JSON：
{
  "hypotheses": [{
    "target_id": "已有偏好ID或空字符串",
    "statement": "可长期验证的心理偏好假设",
    "category": "story|adult|action|character|relationship|visual|boundary|other",
    "polarity": "prefer|avoid",
    "sensitive": false,
    "assessments": [{"evidence_id":"evidence_xxx","direction":"support|against|neutral","strength":"weak|moderate|strong","reason":"为何这样评价"}]
  }],
  "coverage_note": "本轮分析没有覆盖或无法区分的部分",
  "missing_possibilities": ["仍可能存在但当前证据不足的原因"]
}
"""


def update_probability(prior: float, direction: str, strength: str) -> float:
    """Update independent hypothesis odds from an ordinal likelihood ratio."""
    probability = max(0.01, min(0.99, float(prior)))
    ratio = LIKELIHOOD_RATIOS.get((direction, strength), 1.0)
    odds = probability / (1.0 - probability)
    posterior_odds = odds * ratio
    return posterior_odds / (1.0 + posterior_odds)


class PreferenceAnalysisService:
    def __init__(self, ai_engine=None):
        self.ai_engine = ai_engine
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def set_runtime(self, ai_engine=None) -> None:
        self.ai_engine = ai_engine

    def schedule(self, repository, *, enabled: bool, include_sensitive: bool) -> bool:
        if not enabled or not self.ai_engine:
            return False
        evidence = repository.pending_evidence(include_sensitive=include_sensitive)
        if len(evidence) < MIN_EVIDENCE_BATCH:
            return False
        with self._lock:
            if self._running:
                return False
            self._running = True
        thread = threading.Thread(
            target=self._run_guarded,
            args=(repository, include_sensitive),
            name="preference-analysis",
            daemon=True,
        )
        thread.start()
        return True

    def analyze_now(self, repository, *, include_sensitive: bool, force: bool = False) -> dict[str, Any]:
        evidence = repository.pending_evidence(include_sensitive=include_sensitive)
        if force:
            by_id = {str(item.get("id")): item for item in evidence}
            for item in repository.recent_evidence(include_sensitive=include_sensitive):
                by_id.setdefault(str(item.get("id")), item)
            evidence = list(by_id.values())[-24:]
        if not evidence:
            return {"changed": [], "skipped": "没有待分析证据"}
        if not force and len(evidence) < MIN_EVIDENCE_BATCH:
            return {"changed": [], "skipped": f"至少需要 {MIN_EVIDENCE_BATCH} 条有效证据"}
        if not self.ai_engine:
            return {"changed": [], "error": "偏好分析模型不可用"}
        snapshot = repository.analysis_snapshot()
        user_prompt = (
            "【已有偏好与假设】\n" + json.dumps(snapshot, ensure_ascii=False) +
            "\n\n【尚未分析的行为证据】\n" + json.dumps(evidence, ensure_ascii=False)
        )
        raw, error = self.ai_engine.chat_json(
            ANALYSIS_PROMPT, user_prompt, temp=0.3, max_tokens=2600, trace_label="用户偏好深度分析"
        )
        if error or not raw:
            return {"changed": [], "error": error or "偏好分析返回空内容"}
        try:
            payload = robust_json_parse(raw)
        except ValueError as exc:
            return {"changed": [], "error": str(exc)}
        if not isinstance(payload, dict):
            return {"changed": [], "error": "偏好分析必须返回 JSON 对象"}
        changed = repository.apply_analysis(payload, evidence)
        log.info(
            "用户偏好深度分析完成: evidence=%s changed=%s coverage=%s",
            len(evidence), [item.get("id") for item in changed], payload.get("coverage_note", ""),
        )
        return {"changed": changed, "analysis": repository.load().get("analysis", {})}

    def _run_guarded(self, repository, include_sensitive: bool) -> None:
        try:
            result = self.analyze_now(repository, include_sensitive=include_sensitive, force=False)
            if result.get("error"):
                log.warning("用户偏好异步分析失败，正文不受影响: %s", result["error"])
        finally:
            with self._lock:
                self._running = False
