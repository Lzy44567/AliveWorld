import unittest

from core.image_generation.prompt_compiler import ImagePromptCompiler, PromptCompilationError


class FakeAI:
    def __init__(self, response, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.requests.append((system_prompt, user_prompt, kwargs))
        return self.response, self.error


class ImagePromptCompilerTests(unittest.TestCase):
    def test_compiles_structured_prompt_without_starting_provider(self):
        ai = FakeAI('{"positive":"cinematic portrait","negative":"blurry","content_focus":"general","notes":"保留角色服装"}')
        result = ImagePromptCompiler(ai).compile({"intent": "character_portrait", "user_request": "生成肖像", "character_context": "黑发剑士"})
        self.assertEqual(result["positive"], "cinematic portrait")
        self.assertEqual(result["content_focus"], "general")
        self.assertEqual(ai.requests[0][2]["trace_label"], "生图提示词编译")

    def test_explicit_focus_is_preserved_as_model_classification(self):
        ai = FakeAI('{"positive":"adult scene","negative":"","content_focus":"explicit","notes":"按正文表现"}')
        result = ImagePromptCompiler(ai).compile({"story_text": "成人正文", "presentation_level": "露点"})
        self.assertEqual(result["content_focus"], "explicit")

    def test_invalid_or_empty_response_is_rejected(self):
        with self.assertRaises(PromptCompilationError):
            ImagePromptCompiler(FakeAI('{}')).compile({})
        with self.assertRaises(PromptCompilationError):
            ImagePromptCompiler(FakeAI('', "Connection error")).compile({})


if __name__ == "__main__":
    unittest.main()
