import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.request_budget import budget_report, require_budget, normalize_usage
from core.prompt_studio import PromptOverrideStore, list_slices
from core.overseer_prompt_builder import build_overseer_request
from core.model_connections.models import ConnectionProfile, ResolvedConnection
from tests import test_ai_engine as ai_fixture
from core.game_session import GameSession
from core.entities import Entity
from core.request_diagnostics import record_request, recent_requests
from core.model_connections.runtime import ModelConnectionRuntime
from core.model_connections.repository import ConnectionRepository


class RequestBudgetTests(unittest.TestCase):
    def test_overflow_blocks_transport_without_mutating_messages(self):
        engine, create = ai_fixture.AIEngineTests().make_engine([ai_fixture.completion('{}')])
        engine.budget_options = {"context_window": 8192}
        text = "资料" * 10000
        with patch("core.ai_engine.finish_llm_trace") as finish:
            _, error = engine.chat_json("必要规则", text, prompt_manifest=[{"sliceId": "story.history", "estimatedTokens": 18000}])
        self.assertIn("context_budget_exceeded", error)
        self.assertIn("story.history", error)
        create.assert_not_called()
        self.assertFalse(finish.call_args.kwargs["metadata"]["budget"]["fits"])

    def test_usage_missing_and_zero_have_different_meanings(self):
        self.assertIsNone(normalize_usage({})["cacheHitTokens"])
        self.assertEqual(normalize_usage({})["cacheStatus"], "unavailable")
        self.assertEqual(normalize_usage({"prompt_tokens_details": {"cached_tokens": 0}})["cacheHitTokens"], 0)
        report = normalize_usage({"prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 12})
        self.assertEqual((report["cacheHitTokens"], report["cacheMissTokens"]), (100, 12))

    def test_success_metadata_records_budget_usage_and_elapsed_time(self):
        engine, create = ai_fixture.AIEngineTests().make_engine([ai_fixture.completion('{}')])
        with patch("core.ai_engine.finish_llm_trace") as finish:
            engine.chat_json("规则", "行动", max_tokens=1500)
        metadata = finish.call_args.kwargs["metadata"]
        self.assertEqual(metadata["normalizedUsage"]["inputTokens"], 10)
        self.assertEqual(metadata["budget"]["outputReserve"], create.call_args.kwargs["max_tokens"])
        self.assertEqual(metadata["budget"]["outputReserve"], 1500)
        self.assertGreaterEqual(metadata["elapsedMs"], 0)

    def test_required_rules_and_output_reserve_are_never_silently_cut(self):
        report = budget_report("固定规则" * 9000, "玩家行动", 9000, {"context_window": 8192})
        with self.assertRaises(ValueError):
            require_budget(report)
        self.assertEqual(report["omitted"], [])

    def test_connection_budget_validation_and_config_projection(self):
        with self.assertRaises(ValueError):
            ConnectionProfile("a", "a", "text", "openai_compatible", advanced_options={"context_window": -1})
        profile = ConnectionProfile("a", "a", "text", "openai_compatible", advanced_options={"context_window": 64000, "irrelevant": 1})
        self.assertEqual(ResolvedConnection("story", profile).ai_config()["budget_options"], {"context_window": 64000})

    def test_overseer_has_stable_system_prefix_and_real_readonly_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PromptOverrideStore(Path(tmp) / "overrides.json")
            first = build_overseer_request("规则{entities_info}{world_context}", "实体甲", "场景甲", store=store)
            second = build_overseer_request("规则{entities_info}{world_context}", "实体乙", "场景乙", store=store)
            self.assertEqual(first.system_prompt, second.system_prompt)
            self.assertNotIn("实体甲", first.system_prompt)
            self.assertIn("实体甲", first.user_prompt)
            self.assertEqual(first.prompt_manifest[0]["sliceId"], "undercurrent.core")
            views = {v["id"]: v for v in list_slices(store)}
            self.assertEqual(views["undercurrent.core"]["migrationStatus"], "integrated")
            self.assertEqual(views["world.capture.runtime"]["migrationStatus"], "unmigrated")

    def test_overseer_receives_proposed_state_and_no_style_or_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = GameSession(None, "test", tmp)
            session.ctx_mgr.world_info_base = "世界约束"
            session.ctx_mgr.style_info = "不得传入的文风"
            session.undercurrent.entities = [Entity(name="组织甲", motive="观察")]
            plan = session.state_mgr.plan_updates({"status_updates": {"地点": "终点"}})
            context = session._overseer_context("走到终点", "已经到达", plan, {"accepted_facts": ["已到达"]}, [])
            self.assertIn("终点", context)
            self.assertIn("已到达", context)
            self.assertNotIn("不得传入的文风", context)
            self.assertNotIn("地点", session.state["properties"])

    def test_recent_diagnostics_do_not_retain_prompt_or_response(self):
        record_request("test", "diagnostic-id", {"budget": {"fits": True}, "response": "private", "system": "secret"})
        report = recent_requests()[0]
        self.assertNotIn("private", str(report))
        self.assertNotIn("secret", str(report))
        report["budget"]["fits"] = False
        self.assertTrue(recent_requests()[0]["budget"]["fits"])

    def test_budget_change_replaces_cached_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = ConnectionRepository(Path(tmp) / "config.yml")
            repo.path.write_text("api_key: test\nbase_url: http://localhost\nmodel: test\n", encoding="utf-8")
            runtime = ModelConnectionRuntime(repo, engine_factory=lambda config: dict(config))
            first = runtime.engine("story")
            resolved = runtime.resolved("story")
            resolved.profile.advanced_options["context_window"] = 64000
            second = runtime.engine("story")
            self.assertIsNot(first, second)
            self.assertEqual(second["budget_options"]["context_window"], 64000)


if __name__ == "__main__":
    unittest.main()
