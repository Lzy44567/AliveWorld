import logging
import unittest

from core.llm_trace import begin_llm_trace, finish_llm_trace


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []
        self.records = []

    def emit(self, record):
        self.messages.append(record.getMessage())
        self.records.append(record)


class LLMTraceTests(unittest.TestCase):
    def test_trace_records_exact_prompts_and_response_without_credentials(self):
        logger = logging.getLogger("AliveWorld")
        handler = _CaptureHandler()
        previous_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            trace_id = begin_llm_trace("测试阶段", "test-model", "世界书标记", "玩家行动", "json")
            finish_llm_trace("测试阶段", trace_id, response='{"ok": true}')
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)

        output = "\n".join(handler.messages)
        self.assertIn("[SYSTEM]\n世界书标记", output)
        self.assertIn("[USER]\n玩家行动", output)
        self.assertIn('{"ok": true}', output)
        self.assertNotIn("api_key", output)
        self.assertEqual(len(handler.records), 2)
        self.assertEqual(handler.records[0].aw_trace_id, handler.records[1].aw_trace_id)
        self.assertEqual(handler.records[0].aw_phase, "request")
        self.assertEqual(handler.records[1].aw_status, "success")


if __name__ == "__main__":
    unittest.main()
