import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.world_change_events import validate_world_change_events, confirmed_world_changes, SIGNAL_INSTRUCTION
from core.worldbook_capture import WorldbookCaptureService, capture_requested
from core.settlement_contract import validate_settlement, SettlementContractError
from tests.test_worldbook_capture import FakeAI
from tests.test_game_action_suggestions import FakeResolver
from core.game_session import GameSession


def event(evidence="法令今日生效。", **changes):
    return {"summary": "新规则成立", "fact_status": "confirmed", "change_kind": "add",
            "scope_hint": "organization", "time_hint": "persistent", "evidence": evidence, **changes}


class WorldChangeEventTests(unittest.TestCase):
    def test_session_passes_confirmed_events_and_respects_feature_switch(self):
        for enabled, events, expected in ((True, [event()], 1), (True, [], 0), (False, [event()], 0)):
            with self.subTest(enabled=enabled, events=events), tempfile.TemporaryDirectory() as tmp:
                session = GameSession(None, "signal-test", tmp, {"worldbookCaptureEnabled": enabled})
                session.start_new_game("", "开场")
                payload = FakeResolver([]).resolve(session, "继续")
                payload["settlement"].update(story_text="法令今日生效。", world_change_events=events)
                session.resolver = Mock()
                session.resolver.resolve.return_value = payload
                session.worldbook_capture.schedule = Mock()
                session.process_turn("继续")
                session.worldbook_capture.schedule.assert_not_called()
                session.dispatch_committed_worldbook_captures()
                self.assertEqual(session.worldbook_capture.schedule.call_count, expected)
                if expected:
                    self.assertEqual(session.worldbook_capture.schedule.call_args.kwargs["world_change_events"], events)

    def test_generic_confirmed_signals_do_not_need_command_words(self):
        cases = [
            ("此界从此禁止飞行。", "global", "persistent", "add"),
            ("新法令今日生效。", "organization", "persistent", "update"),
            ("结界内重力倒转，直到结界解除。", "location", "until_condition", "add"),
            ("人们相信旧王仍在，但那并非事实。", "group", "persistent", "add"),
            ("历史与档案一并改变。", "global", "persistent", "update"),
            ("禁飞领域的一刻钟时限已经结束。", "region", "fixed_duration", "expire"),
        ]
        for story, scope, duration, kind in cases:
            with self.subTest(story=story):
                signal = event(story, scope_hint=scope, time_hint=duration, change_kind=kind)
                payload = validate_settlement({"story_text": story, "world_change_events": [signal]})
                self.assertTrue(capture_requested(payload, "继续"))
                self.assertEqual(confirmed_world_changes(payload), [signal])

    def test_unconfirmed_or_empty_events_override_legacy_and_aliases(self):
        for status in ("attempted", "reported", "uncertain"):
            payload = {"story_text": "法令今日生效。", "worldbook_capture_needed": True,
                       "world_change_events": [event(fact_status=status)]}
            self.assertFalse(capture_requested(payload, "常识改变：规则改变"))
        for events in ([], None, "bad", [{}]):
            self.assertFalse(capture_requested({"worldbook_capture_needed": True, "world_change_events": events}, "常识恢复"))

    def test_evidence_must_be_a_real_story_excerpt(self):
        self.assertFalse(capture_requested({"story_text": "尝试失败。", "world_change_events": [event()]}))
        self.assertFalse(capture_requested({"world_change_events": [event()]}))

    def test_invalid_contract_rejects_enum_type_size_and_empty_evidence(self):
        values = [None, {}, [event()] * 9, [event(fact_status=True)], [event(change_kind="delete_all")],
                  [event(scope_hint="anything")], [event(time_hint="forever")], [event(evidence=" ")],
                  [event(summary="a" * 301)]]
        for value in values:
            with self.subTest(value=value), self.assertRaises(SettlementContractError):
                validate_settlement({"story_text": "正文", "world_change_events": value})
        self.assertEqual(validate_world_change_events([event(), event()]), [event()])

    def test_legacy_output_stays_compatible(self):
        self.assertTrue(capture_requested(validate_settlement({"story_text": "正文", "worldbook_capture_needed": True})))
        self.assertNotIn("world_change_events", validate_settlement({"story_text": "正文"}))

    def test_detail_capture_rechecks_events_before_model_call(self):
        ai = FakeAI('{"candidates":[]}')
        service = WorldbookCaptureService(ai)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.yml"
            path.write_text("name: test\nentries: []\n", encoding="utf-8")
            for events in ([], [event(fact_status="attempted")], [event("不存在的证据")]):
                service.capture(path, "继续", "法令今日生效。", review_all=True, world_change_events=events)
            self.assertEqual(ai.calls, 0)
            service.capture(path, "继续", "法令今日生效。", review_all=True, world_change_events=[event()])
            self.assertEqual(ai.calls, 1)
            signal_json = ai.last_user_prompt.split("【已校验世界变化信号】\n", 1)[1].split("\n【玩家行动】", 1)[0]
            self.assertEqual(json.loads(signal_json), [event()])
            self.assertIn("群体认知", ai.last_system_prompt)
            self.assertNotIn("常识改变", SIGNAL_INSTRUCTION)

    def test_temporary_or_restoration_signal_cannot_auto_publish(self):
        candidate = {"name": "局部规则", "content": "领域持续期间禁飞", "risk": "low",
                     "scope": "natural_law", "confidence": "high"}
        for signal in (event(time_hint="until_condition"), event(change_kind="restore")):
            with self.subTest(signal=signal), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "book.yml"
                path.write_text("name: test\nentries: []\n", encoding="utf-8")
                ai = FakeAI(json.dumps({"candidates": [candidate]}))
                result = WorldbookCaptureService(ai).capture(path, "继续", "法令今日生效。", review_all=False, world_change_events=[signal])
                self.assertEqual(result["added"], [])
                self.assertEqual(len(result["pending"]), 1)


if __name__ == "__main__":
    unittest.main()
