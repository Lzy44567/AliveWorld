import json
import os
from pathlib import Path
import tempfile
import unittest

from core.preference_workshop import PreferenceWorkshop, PreferenceWorkshopError
from core.preference_workshop_agent import PreferenceWorkshopAgent
from core.user_preferences import UserPreferenceRepository


def preference(preference_id="preference_one", statement="喜欢缓慢关系发展", status="active"):
    return {
        "id": preference_id,
        "statement": statement,
        "category": "relationship",
        "polarity": "prefer",
        "status": status,
        "confidence": 0.8,
        "posterior": 0.8,
        "evidence_count": 2,
        "evidence": [],
    }


class PreferenceWorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = UserPreferenceRepository(os.path.join(self.temp_dir.name, "preferences.yml"))
        self.repository.save({
            "preferences": [preference()],
            "evidence": [{"id": "evidence_one", "summary": "测试证据", "analyzed": True}],
            "analysis": {"coverage_note": "测试"},
        })
        self.workshop = PreferenceWorkshop("workshop_test", self.repository.load())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_draft_is_isolated_until_publish(self):
        self.workshop.apply_operations([{
            "op": "update_preference",
            "preference_id": "preference_one",
            "changes": {"statement": "喜欢有铺垫的关系发展"},
        }], confirm_high_risk=True)
        self.assertEqual(self.repository.load()["preferences"][0]["statement"], "喜欢缓慢关系发展")
        self.workshop.publish(self.repository)
        self.assertEqual(self.repository.load()["preferences"][0]["statement"], "喜欢有铺垫的关系发展")

    def test_activation_and_delete_require_confirmation_for_ai_flow(self):
        result = self.workshop.apply_operations([{
            "op": "delete_preference", "preference_id": "preference_one",
        }], confirm_high_risk=False)
        self.assertEqual(result["applied"], [])
        self.assertEqual(len(self.workshop.draft), 1)
        operation_id = self.workshop.pending[0]["operation_id"]
        self.workshop.approve(operation_id)
        self.assertEqual(self.workshop.draft, [])

    def test_publish_replays_operations_on_latest_profile_and_preserves_evidence(self):
        self.workshop.apply_operations([{
            "op": "update_preference", "preference_id": "preference_one",
            "changes": {"statement": "喜欢关系逐步积累"},
        }], confirm_high_risk=True)
        live = self.repository.load()
        live["preferences"].append(preference("preference_new_live", "游玩中新形成的偏好", "candidate"))
        live["evidence"].append({"id": "evidence_live", "summary": "工坊期间的新证据", "analyzed": False})
        self.repository.save(live)
        self.workshop.publish(self.repository)
        published = self.repository.load()
        self.assertEqual(len(published["preferences"]), 2)
        self.assertEqual(published["preferences"][0]["statement"], "喜欢关系逐步积累")
        self.assertEqual({item["id"] for item in published["evidence"]}, {"evidence_one", "evidence_live"})

    def test_rebase_keeps_live_additions_and_unpublished_edits(self):
        self.workshop.apply_operations([{
            "op": "update_preference", "preference_id": "preference_one",
            "changes": {"statement": "工坊中的新表述"},
        }], confirm_high_risk=True)
        profile = self.repository.load()
        profile["preferences"].append(preference("preference_live", "游玩期间新增", "candidate"))
        self.workshop.rebase(profile)
        self.assertEqual(len(self.workshop.draft), 2)
        self.assertEqual(self.workshop.draft[0]["statement"], "工坊中的新表述")
        self.assertEqual(self.workshop.draft[1]["id"], "preference_live")

    def test_undo_and_persisted_resume_restore_draft(self):
        self.workshop.apply_operations([{
            "op": "set_status", "preference_id": "preference_one", "status": "disabled",
        }], confirm_high_risk=True)
        directory = Path(self.temp_dir.name) / "workshops"
        path = self.workshop.save_session(directory)
        resumed = PreferenceWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(resumed.draft[0]["status"], "disabled")
        resumed.undo()
        self.assertEqual(resumed.draft[0]["status"], "active")

    def test_unknown_fields_and_probability_edits_are_rejected(self):
        self.workshop.apply_operations([{
            "op": "update_preference", "preference_id": "preference_one",
            "changes": {"posterior": 0.01, "confidence": 0.01, "statement": "新表述"},
        }], confirm_high_risk=True)
        item = self.workshop.draft[0]
        self.assertEqual(item["posterior"], 0.8)
        self.assertEqual(item["confidence"], 0.8)
        self.assertEqual(item["statement"], "新表述")
        with self.assertRaises(PreferenceWorkshopError):
            self.workshop.apply_operations([{"op": "rewrite_profile"}])


class FakeEngine:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def chat_json(self, system_prompt, user_prompt, **_kwargs):
        self.prompts.append((system_prompt, user_prompt))
        return json.dumps(self.payload, ensure_ascii=False), None


class PreferenceWorkshopAgentTests(unittest.TestCase):
    def test_discussion_mode_keeps_operations_as_reviewable_proposal(self):
        workshop = PreferenceWorkshop("agent_test", {"preferences": [preference()]})
        engine = FakeEngine({
            "collaboration_stage": "propose",
            "understanding": "玩家希望区分慢节奏和拖沓。",
            "alternative_explanations": ["也可能只是不喜欢无效重复"],
            "design_notes": ["应强调关系进展有积累"],
            "message": "建议先修改表述。",
            "operations": [{
                "op": "update_preference", "preference_id": "preference_one",
                "changes": {"statement": "偏好有持续积累的慢节奏关系发展"},
            }],
            "suggested_actions": ["确认这个表述是否准确"],
        })
        result = PreferenceWorkshopAgent(engine).respond(
            workshop, "慢节奏不等于什么都不发生", "refine", [], commit_changes=False
        )
        self.assertEqual(workshop.draft[0]["statement"], "喜欢缓慢关系发展")
        self.assertEqual(len(result["proposed"]), 1)
        self.assertIn("仍需保留的其他解释", result["message"])

    def test_sensitive_evidence_is_excluded_by_default(self):
        workshop = PreferenceWorkshop("agent_sensitive", {"preferences": []}, include_sensitive=False)
        engine = FakeEngine({
            "collaboration_stage": "explore", "understanding": "证据不足",
            "alternative_explanations": [], "design_notes": [], "message": "继续讨论",
            "operations": [], "suggested_actions": [],
        })
        PreferenceWorkshopAgent(engine).respond(
            workshop, "帮我看看现有证据", "discover",
            [{"id": "safe", "summary": "普通证据", "sensitive": False},
             {"id": "secret", "summary": "敏感证据内容", "sensitive": True}],
        )
        prompt = engine.prompts[0][1]
        self.assertIn("普通证据", prompt)
        self.assertNotIn("敏感证据内容", prompt)

    def test_prompt_does_not_send_nested_raw_evidence_from_draft(self):
        item = preference()
        item["evidence"] = [{"player_action": "不应发送的原始行动"}]
        item["assessments"] = [{"reason": "不应重复发送的分析细节"}]
        workshop = PreferenceWorkshop("agent_projection", {"preferences": [item]})
        engine = FakeEngine({
            "collaboration_stage": "design", "understanding": "检查表述",
            "alternative_explanations": [], "design_notes": [], "message": "暂不修改",
            "operations": [], "suggested_actions": [],
        })
        PreferenceWorkshopAgent(engine).respond(workshop, "检查一下", "refine", [])
        prompt = engine.prompts[0][1]
        self.assertIn("喜欢缓慢关系发展", prompt)
        self.assertNotIn("不应发送的原始行动", prompt)
        self.assertNotIn("不应重复发送的分析细节", prompt)


if __name__ == "__main__":
    unittest.main()
