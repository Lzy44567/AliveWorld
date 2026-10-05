import json
import unittest
from unittest.mock import patch

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

    def test_character_contract_is_exact_and_separate_from_story(self):
        response = self._chat("任务 character.reply", json.dumps({
            "presentation_mode": "roleplay", "current_input": {"content": "你好，中文与emoji🙂"},
        }, ensure_ascii=False))
        raw = response.json()["choices"][0]["message"]["content"]
        output = json.loads(raw)
        self.assertEqual(set(output), {"reply", "ledger_ops"})
        self.assertEqual(output["ledger_ops"], [])
        self.assertIn("roleplay", output["reply"])
        self.assertIn("你好，中文与emoji🙂", output["reply"])
        self.assertEqual(self.client.get("/__test__/requests").json()["requests"][0]["kind"], "character.reply")

    def test_character_v2_selected_only_by_explicit_protocol_marker(self):
        data = {'reply_contract_id': 'character.reply.v2', 'current_input': {'content': '你好'}}
        raw = self._chat('character.reply.v2', json.dumps(data)).json()['choices'][0]['message']['content']
        self.assertEqual({'reply', 'ledger_ops', 'memory_annotations'}, set(json.loads(raw)))
        del data['reply_contract_id']
        raw = self._chat('character.reply.v2', json.dumps(data)).json()['choices'][0]['message']['content']
        self.assertEqual({'reply', 'ledger_ops'}, set(json.loads(raw)))

    def test_character_sse_streams_only_once_and_finishes_strict_json(self):
        with patch("tests.fakes.fake_openai_app.time.sleep") as delay:
            response = self.client.post("/v1/chat/completions", json={
                "model": "fake-story", "stream": True,
                "messages": [{"role": "system", "content": "任务 character.reply"},
                             {"role": "user", "content": json.dumps({"current_input": {"content": "字符🙂测试"}})}],
            })
        frames = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith("data: ") and line != "data: [DONE]"]
        self.assertGreater(delay.call_count, 2)
        output = json.loads("".join(frame["choices"][0]["delta"].get("content", "") for frame in frames))
        self.assertEqual(set(output), {"reply", "ledger_ops"})
        self.assertIn("字符🙂测试", output["reply"])
        self.assertEqual(frames[-1]["choices"][0]["finish_reason"], "stop")
        records = self.client.get("/__test__/requests").json()["requests"]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["stream"])

    def test_character_malformed_fixture_does_not_change_normal_contract(self):
        response = self._chat("任务 character.reply", json.dumps({
            "current_input": {"content": "【角色坏JSON】合成故障"},
        }))
        raw = response.json()["choices"][0]["message"]["content"]
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw)
        self.assertTrue(raw.endswith(" trailing"))

    def test_character_ledger_has_exact_current_message_evidence_and_visibility(self):
        message = {"message_id": "user-message", "content": "【角色账本】我喜欢蓝色🙂"}
        payload = {"current_user_message": message, "participants": [
            {"instance_id": "ai-id", "controller": "ai"},
            {"instance_id": "user-id", "controller": "user"},
        ]}
        raw = self._chat("character.reply", json.dumps(payload, ensure_ascii=False)).json()["choices"][0]["message"]["content"]
        output = json.loads(raw)
        self.assertEqual(set(output), {"reply", "ledger_ops"})
        public, private = output["ledger_ops"]
        self.assertEqual(public["visibility"]["audience_instance_ids"], ["ai-id", "user-id"])
        self.assertEqual(private["visibility"]["audience_instance_ids"], ["ai-id"])
        self.assertEqual(public["source"]["type"], "player_statement")
        self.assertEqual(private["source"]["type"], "model_inference")
        for operation in output["ledger_ops"]:
            self.assertEqual(operation["source"]["message_ids"], [message["message_id"]])
            self.assertEqual(operation["source"]["evidence"], [{"message_id": message["message_id"], "quote": message["content"]}])
            self.assertNotIn("subject_instance_id", operation)

    def test_character_once_failure_succeeds_only_on_explicit_second_call(self):
        payload = json.dumps({"current_user_message": {"content": "【角色一次失败】重试"}})
        first = self._chat("character.reply", payload).json()["choices"][0]["message"]["content"]
        with self.assertRaises(json.JSONDecodeError):
            json.loads(first)
        second = self._chat("character.reply", payload).json()["choices"][0]["message"]["content"]
        self.assertEqual(set(json.loads(second)), {"reply", "ledger_ops"})
        self.assertEqual(len(self.client.get("/__test__/requests").json()["requests"]), 2)

    def test_real_sse_chunks_preserve_json_and_record_one_request(self):
        with patch("tests.fakes.fake_openai_app.time.sleep"):
            response = self.client.post("/v1/chat/completions", json={
                "model": "fake-story", "stream": True,
                "messages": [{"role": "system", "content": "你是游戏地下城主。"}],
            })
        self.assertIn("text/event-stream", response.headers["content-type"])
        chunks = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith("data: ") and line != "data: [DONE]"]
        self.assertGreater(len(chunks), 2)
        raw = "".join(item["choices"][0]["delta"].get("content", "") for item in chunks)
        self.assertIn("自动测试正文1", json.loads(raw)["story_text"])
        self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "stop")
        records = self.client.get("/__test__/requests").json()["requests"]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["stream"])

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
        first_content = first["choices"][0]["message"]["content"]
        self.assertIn("自动测试正文1", first_content)
        first_payload = json.loads(first_content)
        self.assertEqual(first_payload["dynamic_bars"]["自动验收进度"]["current"], 1)
        self.assertEqual(first_payload["status_updates"]["自动验收阶段"], "第1回合")
        second = self._chat("你是游戏地下城主。", "历史：自动测试正文1\n继续").json()
        second_content = second["choices"][0]["message"]["content"]
        self.assertIn("自动测试正文2", second_content)
        second_payload = json.loads(second_content)
        self.assertEqual(second_payload["dynamic_bars"]["自动验收进度"]["current"], 2)
        self.assertEqual(second_payload["status_updates"]["当前时间"], "自动纪元第2回合")

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
