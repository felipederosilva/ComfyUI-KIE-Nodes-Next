import json
import unittest
from unittest.mock import Mock, patch

from test_generated import load_plugin


class TestModelSpecificChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = load_plugin().nodes.generated

    def operation(self, model):
        return next(
            operation
            for operation in self.generated.load_catalog()["operations"]
            if operation.get("market_catalog_id") == model
        )

    def execute(self, model, result, **kwargs):
        client = Mock()
        client.raw_api_request.return_value = result
        with (
            patch.object(self.generated, "make_client", return_value=client),
            patch.object(self.generated, "_credit_balance", return_value=55),
            patch.object(self.generated, "_credit_receipt", side_effect=lambda _client, outputs, *_args, **_kwargs: outputs),
            patch.object(self.generated, "upload_image_batch", return_value=["https://tempfile.redpandaai.co/photo.png"]),
        ):
            outputs = self.generated._execute_llm(self.operation(model), model, {"prompt": "Describe the shot.", **kwargs})
        return outputs, client.raw_api_request.call_args.kwargs["body"]

    def test_gpt_62_official_effort_and_structured_output(self):
        operation = self.operation("gpt-6-2-sol")
        widgets = self.generated._llm_input_types(operation)["optional"]
        self.assertEqual(widgets["reasoning_effort"][0], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(widgets["reasoning_effort"][1]["default"], "medium")
        self.assertNotIn("max_output_tokens", widgets)
        schema = {"type": "object", "properties": {"shot": {"type": "string"}},
                  "required": ["shot"], "additionalProperties": False}
        outputs, body = self.execute(
            "gpt-6-2-sol",
            {"stream_events": [
                {"type": "response.output_text.delta", "delta": "Shot"},
                {"type": "response.output_text.delta", "delta": " one"},
                {"type": "response.completed", "response": {
                    "id": "resp_1", "usage": {"output_tokens": 2}, "output": [
                        {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Not the answer."}]},
                        {"type": "message", "content": [{"type": "output_text", "text": "Shot one"}]},
                    ],
                }},
            ]},
            reasoning_effort="max", system_prompt="Use one sentence.", output_schema_json=json.dumps(schema),
        )
        self.assertEqual(body["reasoning"], {"effort": "max"})
        self.assertEqual(body["input"][0]["role"], "developer")
        self.assertEqual(body["text"]["format"]["schema"], schema)
        self.assertEqual(outputs[0], "Shot one")
        self.assertEqual(json.loads(outputs[3]), {"output_tokens": 2})

    def test_native_gemini_selects_model_specific_thinking_and_usage(self):
        carbon = self.generated._llm_input_types(self.operation("gemini-4-carbon"))["optional"]
        neon = self.generated._llm_input_types(self.operation("gemini-4-neon"))["optional"]
        self.assertEqual(carbon["reasoning_effort"][0], ["low", "medium", "high"])
        self.assertEqual(neon["reasoning_effort"][0], ["low", "medium", "high", "xhigh"])
        self.assertEqual(neon["images"][0], "IMAGE")
        outputs, body = self.execute(
            "gemini-4-neon",
            {"candidates": [{"content": {"parts": [
                {"thought": True, "text": "Not the answer."},
                {"thoughtSignature": "provider token", "text": "Shot one"},
            ]}}], "usageMetadata": {"totalTokenCount": 7}},
            reasoning_effort="xhigh", include_thoughts=True, images=object(),
        )
        self.assertEqual(body["generationConfig"], {"thinkingConfig": {"thinkingLevel": "xhigh", "includeThoughts": True}})
        self.assertIn("file_data", body["contents"][-1]["parts"][-1])
        self.assertEqual(outputs[0], "Shot one")
        self.assertEqual(json.loads(outputs[3]), {"totalTokenCount": 7})

    def test_openai_compatible_gemini_joins_fragments_without_model_field(self):
        outputs, body = self.execute(
            "gemini-4-neon-openai",
            {"stream_events": [
                {"id": "reply", "choices": [{"delta": {"content": "Shot"}}]},
                {"id": "reply", "choices": [{"delta": {"content": " "}}]},
                {"id": "reply", "choices": [{"delta": {"content": "one"}}]},
                {"id": "reply", "choices": [], "usage": {"completion_tokens": 3}},
            ]},
            stream=True, reasoning_effort="medium", include_thoughts=True,
        )
        self.assertNotIn("model", body)
        self.assertEqual(body["reasoning_effort"], "medium")
        self.assertTrue(body["include_thoughts"])
        self.assertEqual(outputs[0], "Shot one")
        self.assertEqual(json.loads(outputs[3]), {"completion_tokens": 3})

    def test_invalid_reasoning_level_fails_before_starting_a_request(self):
        with patch.object(self.generated, "make_client") as client:
            with self.assertRaisesRegex(ValueError, "reasoning_effort"):
                self.generated._execute_llm(self.operation("gemini-4-carbon"), "gemini-4-carbon",
                                            {"prompt": "Describe this shot.", "reasoning_effort": "xhigh"})
        client.assert_not_called()
