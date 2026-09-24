"""Compose only the projections owned by the undercurrent task."""
from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart


def build_overseer_request(baseline, entities, world, *, store=None):
    # Replace legacy data slots with stable references, preserving authored rules.
    rules = baseline.replace("{entities_info}", "参见 user 消息中的活跃实体资料。")
    rules = rules.replace("{world_context}", "参见 user 消息中的世界与本轮资料。")
    system = compose_prompt("undercurrent", {}, include={"undercurrent.core"},
                            baselines={"undercurrent.core": rules}, store=store)
    return plan_model_request(system, [
        RequestMessagePart("context.active_entities", "【活跃暗流实体】\n" + entities, cache_class="session"),
        RequestMessagePart("context.undercurrent_world", "【世界与本轮资料】\n" + world, "\n"),
        RequestMessagePart("undercurrent.action", "请推演实体的幕后行动与生灭。无动作的数组必须留空 []。", "\n"),
    ], temperature=0.8, max_tokens=None, trace_label="Overseer实体推演", mode="normal", contract_id="undercurrent.v1")
