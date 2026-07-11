import unittest
from unittest.mock import patch

from core.causal_ledger import CausalLedger
from core.resolution_engine import DualTrackResolver


class SequenceAI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.requests.append((system_prompt, user_prompt, kwargs))
        return self.responses.pop(0), None


class FakeUndercurrent:
    def __init__(self, ledger):
        self.causal_ledger = ledger


class FakeSession:
    def __init__(self, ai, ledger):
        self.ai_engine = ai
        self.undercurrent = FakeUndercurrent(ledger)
        self.char_info = "测试角色"
        self.style_info = "测试文风"
        self.word_limit = 200

    def get_context_text(self): return "玩家来到城门"
    def get_dynamic_state_for_ai(self): return {}
    def build_active_world_info(self, _action): return (self.undercurrent.causal_ledger.context(), [])


class CausalResolutionTests(unittest.TestCase):
    def test_matching_influence_is_passed_to_settlement_and_reported(self):
        ledger = CausalLedger()
        influence = ledger.add({
            "summary": "城门盘查", "condition": "玩家进入城门", "effect": "守卫必须盘查玩家",
            "consume_policy": {"mode": "on_success"},
        })
        ai = SequenceAI([
            '{"reactions":[{"id":1,"description":"守卫靠近","weight":100}],"influence_checks":[{"id":"%s","condition_met":true,"reason":"玩家进入城门"}]}' % influence.id,
            '{"story_text":"守卫拦住了玩家。","resolved_influences":[{"id":"%s","result":"守卫开始盘查"}]}' % influence.id,
        ])
        session = FakeSession(ai, ledger)

        with patch("core.resolution_engine.load_system_prompts", return_value={"reaction_prompt": "{world_info}", "settlement_prompt": "结算"}):
            result = DualTrackResolver().resolve(session, "进入城门")

        self.assertEqual(result["triggered_influences"][0]["id"], influence.id)
        self.assertIn("本回合必须兑现", ai.requests[1][1])
        self.assertIn(influence.id, ai.requests[1][1])
        self.assertEqual(result["settlement"]["resolved_influences"][0]["id"], influence.id)

    def test_non_matching_and_unknown_influences_are_not_passed(self):
        ledger = CausalLedger()
        influence = ledger.add({"summary": "远方陷阱", "condition": "进入森林", "effect": "陷阱触发"})
        ai = SequenceAI([
            '{"reactions":[{"id":1,"description":"继续前进","weight":100}],"influence_checks":[{"id":"%s","condition_met":false,"reason":"不在森林"},{"id":"fake","condition_met":true,"reason":"伪造"}]}' % influence.id,
            '{"story_text":"道路平静。","resolved_influences":[]}',
        ])
        session = FakeSession(ai, ledger)

        with patch("core.resolution_engine.load_system_prompts", return_value={"reaction_prompt": "{world_info}", "settlement_prompt": "结算"}):
            result = DualTrackResolver().resolve(session, "沿道路前进")

        self.assertEqual(result["triggered_influences"], [])
        self.assertIn("没有满足条件", ai.requests[1][1])


if __name__ == "__main__":
    unittest.main()
