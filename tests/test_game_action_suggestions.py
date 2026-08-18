import tempfile
import unittest

from core.game_session import GameSession


class FakeResolver:
    def __init__(self, suggestions):
        self.suggestions = suggestions
        self.received_actions = []

    def resolve(self, _session, action):
        self.received_actions.append(action)
        return {
            "reactions": [{"id": 1, "description": "广场保持平静", "eligible": True, "weight": 1, "basis": []}],
            "chosen_reaction": {"id": 1, "description": "广场保持平静", "eligible": True, "weight": 1, "basis": []},
            "triggered_influences": [],
            "settlement": {
                "story_text": "玩家来到广场。",
                "resolved_influences": [],
                "action_suggestions": self.suggestions,
                "worldbook_capture_needed": False,
            },
        }


class RecordingAI:
    def __init__(self):
        self.requests = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.requests.append((system_prompt, user_prompt, kwargs))
        return '{"story_text":"球状闪电击中车门，车辆失控停下。","resolved_influences":[],"preference_evidence":[]}', None


class GameActionSuggestionTests(unittest.TestCase):
    def test_turn_persists_suggestions_on_ai_message_and_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir)
            session.start_new_game("", "开场")
            session.resolver = FakeResolver(["观察广场", "询问路人", "观察广场"])
            session.process_turn("前往广场")

            self.assertEqual(session.action_suggestions, ["观察广场", "询问路人"])
            ai_message = next(message for message in reversed(session.history["chat_messages"]) if message["role"] == "ai")
            self.assertEqual(ai_message["suggestions"], session.action_suggestions)
            self.assertEqual(session.export_save_data()["action_suggestions"], session.action_suggestions)

    def test_turn_discards_suggestions_when_story_setting_is_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir, {"aiSuggestions": False})
            session.start_new_game("", "开场")
            session.resolver = FakeResolver(["不应显示"])
            session.process_turn("等待")
            self.assertEqual(session.action_suggestions, [])

    def test_manual_letter_reference_is_expanded_before_ai_but_keeps_player_bubble(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir)
            session.start_new_game("", "开场")
            session.action_suggestions = ["观察广场", "询问路人"]
            resolver = FakeResolver([])
            session.resolver = resolver
            session.process_turn("B，再隐藏身份")

            self.assertEqual(
                resolver.received_actions[0],
                "【玩家选择的建议行动】询问路人\n【玩家补充】再隐藏身份",
            )
            user_message = next(message for message in session.history["chat_messages"] if message["role"] == "user")
            self.assertEqual(user_message["content"], "B，再隐藏身份")

    def test_rollback_restores_consumed_influence_and_turn_counter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir)
            influence = session.undercurrent.causal_ledger.add({
                "summary": "一次性陷阱", "condition": "玩家靠近", "effect": "陷阱爆炸",
                "type": "one_shot", "consume_policy": {"mode": "on_success"},
            })
            session._take_snapshot()
            session.undercurrent.causal_ledger.advance_turn()
            session.undercurrent.causal_ledger.evaluate_checks([{"id": influence.id, "condition_met": True, "reason": "满足条件"}])
            session.undercurrent.causal_ledger.resolve([{"id": influence.id, "result": "已经爆炸"}])
            self.assertEqual(influence.status, "consumed")

            self.assertTrue(session.rollback())
            restored = session.undercurrent.causal_ledger.by_id(influence.id)
            self.assertEqual(restored.status, "active")
            self.assertEqual(restored.trigger_count, 0)
            self.assertEqual(session.undercurrent.causal_ledger.turn_count, 0)

    def test_reroll_reuses_action_adjudication_instead_of_reinterpreting_player_fact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ai = RecordingAI()
            session = GameSession(ai, "测试", temp_dir, {"entitiesEnabled": False})
            session.start_new_game("", "开场")
            session._take_snapshot()
            session.history["chat_messages"].extend([
                {"role": "user", "content": "我发射球状闪电摧毁囚车"},
                {"role": "action_adjudication", "content": {
                    "accepted_facts": ["玩家成功发射球状闪电"],
                    "contested_outcomes": [{"claim": "囚车被摧毁", "reason": "外部结果"}],
                    "rejected_claims": [],
                }},
                {"role": "reactions", "content": [
                    {"id": 1, "description": "囚车侧翻", "eligible": True, "weight": 1, "basis": []},
                    {"id": 2, "description": "囚车停车", "eligible": True, "weight": 1, "basis": []},
                ]},
                {"role": "influence_checks", "content": []},
                {"role": "system", "content": "命运变数: 囚车侧翻"},
                {"role": "ai", "content": "旧结果"},
            ])

            result = session.reroll_turn()

            self.assertNotIn("error", result)
            self.assertEqual(len(ai.requests), 1)
            self.assertIn("已接受，正文不得否认：玩家成功发射球状闪电", ai.requests[0][1])
            adjudication_messages = [
                item for item in session.history["chat_messages"] if item.get("role") == "action_adjudication"
            ]
            self.assertEqual(adjudication_messages[-1]["content"]["accepted_facts"], ["玩家成功发射球状闪电"])


if __name__ == "__main__":
    unittest.main()
