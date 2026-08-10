import unittest

from fastapi.testclient import TestClient

from tests.fakes.fake_openai_app import app


class FakeOpenAIAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.delete("/__test__/requests")

    def _chat(self, system, user="测试行动"):
        return self.client.post("/v1/chat/completions", json={
            "model": "fake-story",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        })

    def test_models_are_openai_compatible(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fake-story", [item["id"] for item in response.json()["data"]])

    def test_settlement_reports_only_detected_asset_markers(self):
        response = self._chat("你是严谨的游戏地下城主。测试文风；测试角色卡；测试世界书。【AWTEST:自定义预设A】")
        content = response.json()["choices"][0]["message"]["content"]
        self.assertIn("文风就绪", content)
        self.assertIn("角色卡就绪", content)
        self.assertIn("世界书就绪", content)
        self.assertIn("自定义预设A就绪", content)
        records = self.client.get("/__test__/requests").json()["requests"]
        self.assertEqual(records[-1]["kind"], "settlement")
        self.assertIn("自定义预设A", records[-1]["markers"])

    def test_story_sequence_is_derived_from_history_in_prompt(self):
        first = self._chat("你是游戏地下城主。", "开始故事").json()
        self.assertIn("自动测试正文1", first["choices"][0]["message"]["content"])
        second = self._chat("你是游戏地下城主。", "历史：自动测试正文1\n继续").json()
        self.assertIn("自动测试正文2", second["choices"][0]["message"]["content"])

    def test_coverage_groups_markers_by_ai_task(self):
        self._chat("你是游戏地下城主。【AWTEST:正文规则A】")
        self._chat("你是 Overseer。【活跃暗流实体】【AWTEST:实体规则A】")
        coverage = self.client.get("/__test__/coverage").json()
        self.assertEqual(coverage["tasks"]["settlement"], 1)
        self.assertEqual(coverage["tasks"]["overseer"], 1)
        self.assertEqual(coverage["markers"]["正文规则A"]["settlement"], 1)
        self.assertEqual(coverage["markers"]["实体规则A"]["overseer"], 1)

    def test_reaction_and_overseer_have_separate_protocols(self):
        reaction = self._chat("你是一个严谨的近期未来推演器").json()
        self.assertIn("reactions", reaction["choices"][0]["message"]["content"])
        overseer = self._chat("你是 Overseer。【活跃暗流实体】测试实体").json()
        self.assertIn("undercurrent_events", overseer["choices"][0]["message"]["content"])
        kinds = [item["kind"] for item in self.client.get("/__test__/requests").json()["requests"]]
        self.assertEqual(kinds[-2:], ["reaction", "overseer"])


if __name__ == "__main__":
    unittest.main()
