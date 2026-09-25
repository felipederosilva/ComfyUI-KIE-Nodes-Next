import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_generated import load_plugin


class TestPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.kie import capabilities
        from kie_next_testpkg.nodes import generated, preflight, studio
        cls.capabilities, cls.generated, cls.preflight, cls.studio = capabilities, generated, preflight, studio

    def test_explicit_limits_and_boolean_audio(self):
        op = {"parameter_hints": {
            "prompt": {"type": "string", "required": True, "minLength": 3},
            "duration": {"type": "integer", "minimum": 2, "maximum": 15},
            "audio": {"type": "boolean"},
            "resolution": {"enum": ["720p", "1080p"]},
        }}
        report = self.capabilities.check_operation(op, {"prompt": "Hi", "duration": 30, "audio": True, "resolution": "4k"})
        self.assertEqual(len(report["errors"]), 3)
        self.assertFalse(report["valid"])

    def test_media_count_without_url_object_schema_false_positive(self):
        op = {"parameter_hints": {"image_urls": {"type": "array", "maxItems": 1, "items": {"type": "object"}}}}
        report = self.capabilities.check_operation(op, {"image_urls": ["https://example.test/a", "https://example.test/b"]}, media_fields={"image_urls"})
        self.assertEqual(report["errors"], ["image_urls: needs at most 1 items."])

    def test_unknown_schema_and_camera_are_not_claimed_as_supported(self):
        report = self.capabilities.check_operation({"title": "Unknown"}, {})
        self.assertTrue(report["warnings"])
        self.assertEqual(report["capabilities"]["camera"]["mode"], "unknown")
        op = {"parameter_hints": {"prompt": {"type": "string"}}}
        self.assertEqual(self.capabilities.operation_capabilities(op)["camera"]["mode"], "prompt_guidance")

    def test_invalid_generated_inputs_stop_before_client_and_upload(self):
        op = {"endpoint": "/api/v1/jobs/createTask", "parameter_hints": {
            "resolution": {"enum": ["720p"]}, "image_urls": {"type": "array"},
        }}
        with patch.object(self.generated, "make_client") as client, patch.object(self.generated, "upload_image_batch") as upload:
            with self.assertRaisesRegex(ValueError, "resolution"):
                self.generated._market_execute(op, "test/model", "image", {"resolution": "4k", "image_urls": object()})
        client.assert_not_called()
        upload.assert_not_called()

    def test_valid_generation_uploads_exactly_once(self):
        op = {"endpoint": "/api/v1/jobs/createTask", "parameter_hints": {
            "resolution": {"enum": ["720p"]}, "image_urls": {"type": "array", "required": True},
        }}
        client = Mock()
        client.create_task.return_value = "task"
        client.wait_for_task.return_value = SimpleNamespace(raw={}, credits_consumed=1)
        with patch.object(self.generated, "make_client", return_value=client), patch.object(self.generated, "_credit_balance", return_value=10), patch.object(self.generated, "_result_for_kind", return_value=("ok",)), patch.object(self.generated, "upload_image_batch", return_value=["https://example.test/image"]) as upload:
            result = self.generated._market_execute(op, "test/model", "image", {"resolution": "720p", "image_urls": object()})
        self.assertEqual(result, ("ok",))
        upload.assert_called_once()
        self.assertNotIn("preflight.invalid", str(client.create_task.call_args))

    def test_wan_frames_conflict_with_references(self):
        report = self.capabilities.check_operation({}, {"first_frame_url": "frame", "reference_video_urls": ["video"]}, model="wan/3-0-video")
        self.assertFalse(report["valid"])
        self.assertIn("cannot be combined", report["errors"][0])

    def test_seedance_missing_last_frame_never_uploads_first(self):
        node = self.studio.KIESeedanceStudioNode()
        with patch.object(self.studio, "make_client") as client, patch.object(self.studio, "upload_image_batch") as upload:
            with self.assertRaisesRegex(ValueError, "last frame"):
                node.execute(model="bytedance/seedance-2", generation_mode="first + last frame", prompt="A cinematic scene", resolution="720p", aspect_ratio="16:9", duration=5, generate_audio=False, first_frame=object())
        client.assert_not_called()
        upload.assert_not_called()

    def test_seedance_does_not_silently_ignore_connected_references(self):
        with self.assertRaisesRegex(ValueError, "Reference inputs are connected"):
            self.studio.KIESeedanceStudioNode().prepare_request(model="bytedance/seedance-2", generation_mode="text", prompt="A cinematic scene", resolution="720p", aspect_ratio="16:9", duration=5, generate_audio=False, reference_image_1=object(), dry_run=True)

    def test_all_studio_model_defaults_have_no_schema_errors(self):
        for cls in (self.studio.KIESeedanceStudioNode, self.studio.KIEKlingOmniStudioNode):
            inputs = {key: spec[1]["default"] for key, spec in cls.INPUT_TYPES()["required"].items()}
            inputs["prompt"] = "A cinematic scene with a slow camera movement."
            models = cls.INPUT_TYPES()["required"].get("model", ([None],))[0]
            for model in models:
                if model:
                    inputs["model"] = model
                selected, payload = cls().prepare_request(**inputs, dry_run=True)
                report = self.studio._studio_report(selected, payload)
                self.assertTrue(report["valid"], (selected, report["errors"]))

    def test_connected_prompt_is_deferred_without_network(self):
        node_id = next(key for key, cls in self.plugin.NODE_CLASS_MAPPINGS.items() if getattr(cls, "MODEL", "") == "bytedance/seedance-2")
        with patch.object(self.generated, "make_client") as client, patch.object(self.generated, "upload_image_batch") as upload:
            report = self.preflight.inspect_node_inputs(node_id, {"resolution": "720p", "duration": 5}, ["prompt", "first_frame_url"])
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(any("Connected" in text for text in report["warnings"]))
        client.assert_not_called()
        upload.assert_not_called()

    def test_connected_media_still_detects_conflicts_in_menu(self):
        node_id = next(key for key, cls in self.plugin.NODE_CLASS_MAPPINGS.items() if getattr(cls, "MODEL", "") == "bytedance/seedance-2")
        report = self.preflight.inspect_node_inputs(node_id, {"prompt": "A cinematic scene"}, ["first_frame_url", "reference_video_1"])
        self.assertFalse(report["valid"])
        self.assertIn("cannot be combined", report["errors"][0])

    def test_numeric_combo_preserves_documented_json_type(self):
        op = {"parameter_hints": {"duration": {"type": "integer", "enum": [5, 10]}}}
        payload = self.generated._build_payload(None, op, {"duration": "5"}, dry_run=True)
        self.assertEqual(payload["duration"], 5)
        self.assertTrue(self.capabilities.check_operation(op, payload)["valid"])

    def test_nested_required_and_media_limits_survive_catalog_extraction(self):
        from kie_next_testpkg.kie.catalog import _hint_from_schema
        hint = _hint_from_schema({"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}, required=False)
        report = self.capabilities.check_operation({"parameter_hints": {"element": hint}}, {"element": {}})
        self.assertIn("element.name: required.", report["errors"])
        self.assertEqual(_hint_from_schema({"type": "array", "maxItems": 3}, required=False)["maxItems"], 3)

    def test_shot_sequence_does_not_silently_drop_extra_shots(self):
        import json
        with self.assertRaisesRegex(ValueError, "at most 6"):
            self.studio._parse_shots(json.dumps([{"prompt": "A shot", "duration": 1}] * 7))

    def test_chat_preflight_rejects_bad_json_before_client(self):
        op = {"family": "Chat Models > Kimi", "endpoint": "/openai/v1/responses"}
        with patch.object(self.generated, "make_client") as client, patch.object(self.generated, "upload_image_batch") as upload:
            with self.assertRaisesRegex(ValueError, "history_json"):
                self.generated._execute_llm(op, "kimi-k3", {"prompt": "Describe this shot", "history_json": "{}"})
        client.assert_not_called()
        upload.assert_not_called()

    def test_chat_inspection_validates_without_network_and_defers_connected_prompt(self):
        node_id = next(key for key, cls in self.plugin.NODE_CLASS_MAPPINGS.items()
                       if getattr(cls, "MODEL", "") == "kimi-k3")
        with patch.object(self.generated, "make_client") as client:
            bad = self.preflight.inspect_node_inputs(node_id, {"prompt": "", "tools_json": "not json"}, [])
            deferred = self.preflight.inspect_node_inputs(node_id, {"tools_json": "[]"}, ["prompt"])
        self.assertFalse(bad["valid"])
        self.assertTrue(any("tools_json" in message for message in bad["errors"]))
        self.assertTrue(deferred["valid"])
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
