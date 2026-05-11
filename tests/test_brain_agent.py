import unittest

from jarvis.modules.brain import Brain


class MemoryStub:
    def __init__(self):
        self.saved = []

    def recall(self, query, n_results=5):
        return []

    def remember(self, text, metadata=None):
        self.saved.append((text, metadata or {}))


class BrainAgentTests(unittest.TestCase):
    def test_agent_executes_tool_then_returns_final_answer(self):
        brain = Brain({"brain": {}}, MemoryStub())
        responses = iter(
            [
                '{"action":"calculate","args":{"expression":"2 + 3 * 4"}}',
                '{"action":"final","answer":"The result is 14."}',
            ]
        )
        brain._ask_model = lambda prompt: next(responses)

        answer = brain.run_agent("what is 2 + 3 * 4?", max_steps=2)

        self.assertEqual(answer, "The result is 14.")

    def test_calculator_rejects_non_arithmetic(self):
        brain = Brain({"brain": {}}, MemoryStub())

        result = brain._tool_calculate("__import__('os').system('dir')")

        self.assertEqual(result, "Only arithmetic expressions are allowed.")

    def test_agent_memory_tool_saves_fact(self):
        memory = MemoryStub()
        brain = Brain({"brain": {}}, memory)
        responses = iter(
            [
                '{"action":"remember","args":{"text":"The user prefers concise answers."}}',
                '{"action":"final","answer":"I will remember that."}',
            ]
        )
        brain._ask_model = lambda prompt: next(responses)

        answer = brain.run_agent("remember that I prefer concise answers", max_steps=2)

        self.assertEqual(answer, "I will remember that.")
        self.assertEqual(memory.saved[0][0], "The user prefers concise answers.")
        self.assertEqual(memory.saved[0][1]["source"], "agent")

    def test_parse_intent_uses_fast_heuristic_for_open_app(self):
        brain = Brain({"brain": {"use_llm_intent_router": False}}, MemoryStub())

        intent = brain.parse_intent("open notepad")

        self.assertEqual(intent, {"action": "open_app", "args": {"app_name": "notepad"}})

    def test_parse_intent_uses_fast_heuristic_for_whatsapp(self):
        brain = Brain({"brain": {"use_llm_intent_router": False}}, MemoryStub())

        intent = brain.parse_intent("send WhatsApp to +91 98765 43210 saying hello boss")

        self.assertEqual(
            intent,
            {
                "action": "send_whatsapp",
                "args": {"phone": "+919876543210", "message": "hello boss"},
            },
        )

    def test_tool_manifest_does_not_expose_handlers(self):
        brain = Brain({"brain": {}}, MemoryStub())

        manifest = brain.tool_manifest()

        self.assertTrue(any(tool["name"] == "calculate" for tool in manifest))
        self.assertFalse(any("handler" in tool for tool in manifest))


if __name__ == "__main__":
    unittest.main()
