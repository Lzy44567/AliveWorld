"""Provider-neutral request limits and usage evidence; never truncate source data."""
import math


def estimate_tokens(text):
    return math.ceil(len(str(text).encode("utf-8")) / 3.2)


def budget_report(system, user, output_tokens=None, options=None, manifest=None):
    options = options or {}
    window = int(options.get("context_window") or 32768)
    # A player's connection setting overrides a task's built-in default.
    reserve = int(options.get("output_reserve") or output_tokens or 8192)
    margin = math.ceil(window * 0.1)
    estimated = estimate_tokens(system) + estimate_tokens(user) + 16
    return {
        "contextWindow": window, "windowSource": "configured" if options.get("context_window") else "conservative_default",
        "outputReserve": reserve, "margin": margin, "inputLimit": window - reserve - margin,
        "estimatedInputTokens": estimated, "estimator": "utf8_bytes_div_3.2_estimate",
        "fits": estimated <= window - reserve - margin, "omitted": [],
        "sources": [{"id": p.get("sliceId"), "estimatedTokens": p.get("estimatedTokens", 0)} for p in (manifest or [])],
    }


def require_budget(report):
    if not report["fits"]:
        largest = sorted(report["sources"], key=lambda p: p["estimatedTokens"], reverse=True)[:3]
        sources = ", ".join(f"{p['id']}≈{p['estimatedTokens']}" for p in largest)
        raise ValueError(
            f"context_budget_exceeded: 输入估算 {report['estimatedInputTokens']} tokens，"
            f"可用 {report['inputLimit']}（已预留输出与误差）。主要来源：{sources or 'system/user'}。"
            "请压缩历史、调整载入资产，或在接口高级设置中核实上下文窗口。"
        )


def normalize_usage(raw):
    raw = raw if isinstance(raw, dict) else {}
    def count(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    details = raw.get("prompt_tokens_details") or {}
    hit = count(raw.get("prompt_cache_hit_tokens"))
    if hit is None and isinstance(details, dict):
        hit = count(details.get("cached_tokens"))
    return {
        "inputTokens": count(raw.get("prompt_tokens")),
        "outputTokens": count(raw.get("completion_tokens")),
        "totalTokens": count(raw.get("total_tokens")),
        "cacheHitTokens": hit,
        "cacheMissTokens": count(raw.get("prompt_cache_miss_tokens")),
        "cacheStatus": "reported" if hit is not None else "unavailable",
    }
