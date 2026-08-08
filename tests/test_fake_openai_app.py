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
        response = self._chat("你是严谨的游戏地下城主。测试文风；测试角色卡；测试世界书。")
        content = response.json()["choices"][0]["message"]["content"]
        self.assertIn("文风就绪", content)
        self.assertIn("角色卡就绪", content)
        self.assertIn("世界书就绪", content)
        records = self.client.get("/__test__/requests").json()["requests"]
        self.assertEqual(records[-1]["kind"], "settlement")

    def test_reaction_and_overseer_have_separate_protocols(self):
        reaction = self._chat("你是一个严谨的近期未来推演器").json()
        self.assertIn("reactions", reaction["choices"][0]["message"]["content"])
        overseer = self._chat("你是 Overseer。【活跃暗流实体】测试实体").json()
        self.assertIn("undercurrent_events", overseer["choices"][0]["message"]["content"])
        kinds = [item["kind"] for item in self.client.get("/__test__/requests").json()["requests"]]
        self.assertEqual(kinds[-2:], ["reaction", "overseer"])


if __name__ == "__main__":
    unittest.main()
