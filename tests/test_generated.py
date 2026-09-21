import importlib.util
import json
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_plugin():
    name = "kie_next_testpkg"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestGeneratedNodes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def find(self, display):
        for node_id, name in self.plugin.NODE_DISPLAY_NAME_MAPPINGS.items():
            if name == display:
                return self.plugin.NODE_CLASS_MAPPINGS[node_id]
        self.fail(f"node not found: {display}")

    def test_any_api_is_not_registered(self):
        names = self.plugin.NODE_DISPLAY_NAME_MAPPINGS.values()
        self.assertFalse(any("Any KIE API" in x for x in names))

    def test_seedance_folder_and_native_reference_inputs(self):
        node = self.find("Seedance 2.0")
        self.assertEqual(node.CATEGORY, "KIE Next/Video/ByteDance/Seedance")
        inputs = node.INPUT_TYPES()
        self.assertEqual(inputs["required"]["prompt"][0], "STRING")
        self.assertTrue(inputs["required"]["prompt"][1].get("multiline"))
        self.assertEqual(inputs["optional"]["first_frame_url"][0], "IMAGE")
        self.assertEqual(inputs["optional"]["last_frame_url"][0], "IMAGE")
        self.assertEqual(inputs["optional"]["reference_video_1"][0], "VIDEO")
        self.assertEqual(inputs["optional"]["reference_audio_1"][0], "AUDIO")

    def test_claude_opus_folder_is_individual(self):
        node = self.find("Claude Opus 5")
        self.assertEqual(node.CATEGORY, "KIE Next/LLM/Claude/Opus")
        inputs = node.INPUT_TYPES()
        self.assertIn("thinking", inputs["optional"])
        self.assertNotIn("web_search", inputs["optional"])

    def test_gpt_folder_is_individual(self):
        node = self.find("GPT 5.6 Sol")
        self.assertEqual(node.CATEGORY, "KIE Next/LLM/OpenAI/GPT")
        inputs = node.INPUT_TYPES()
        self.assertIn("reasoning_effort", inputs["optional"])
        self.assertIn("web_search", inputs["optional"])
        self.assertIn("images", inputs["optional"])

    def test_direct_api_model_enum_becomes_individual_nodes(self):
        node = self.find("Generate Music · V5.5")
        self.assertEqual(node.CATEGORY, "KIE Next/Audio/Suno/Music Generation")
        inputs = node.INPUT_TYPES()
        self.assertNotIn("model", inputs["required"])
        self.assertNotIn("model", inputs["optional"])
        self.assertIn("prompt", inputs["required"])

    def test_suno_market_envelope_and_payload_model_are_distinct(self):
        generated = self.plugin.nodes.generated
        op = {
            "endpoint": "/api/v1/jobs/createTask",
            "docs_url": "https://docs.kie.ai/suno-api/generate-music.md",
            "example_body": {"prompt": "test", "model": "V4"},
            "parameter_hints": {"prompt": {"required": True}, "model": {"required": True}},
        }
        self.assertEqual(generated._market_envelope_model(op, "V6_WILD"), "ai-music-api/generate")
        payload = generated._build_payload(None, op, {"prompt": "test"}, model="V6_WILD")
        self.assertEqual(payload["model"], "V6_WILD")

    def test_suno_unversioned_market_node_uses_documented_envelope(self):
        generated = self.plugin.nodes.generated
        op = {
            "endpoint": "/api/v1/jobs/createTask",
            "docs_url": "https://docs.kie.ai/suno-api/cover-suno.md",
        }
        self.assertEqual(generated._market_envelope_model(op), "ai-music-api/cover-generate")

    def test_suno_market_submission_keeps_envelope_and_input_version_separate(self):
        generated = self.plugin.nodes.generated
        op = {
            "endpoint": "/api/v1/jobs/createTask",
            "docs_url": "https://docs.kie.ai/suno-api/generate-music.md",
            "example_body": {"prompt": "test", "model": "V4"},
            "parameter_hints": {"prompt": {"required": True}, "model": {"required": True}},
        }

        class FakeClient:
            def create_task(self, model, payload, callback_url=""):
                self.submission = (model, payload, callback_url)
                return "task-1"

            def wait_for_task(self, task_id, timeout_seconds):
                return SimpleNamespace(raw={}, urls=[], credits_consumed=0.0)

        fake = FakeClient()
        with patch.object(generated, "make_client", return_value=fake):
            generated._market_execute(
                op,
                "ai-music-api/generate",
                "utility",
                {"prompt": "test"},
                payload_model="V6_WILD",
            )

        self.assertEqual(fake.submission[0], "ai-music-api/generate")
        self.assertEqual(fake.submission[1]["model"], "V6_WILD")

    def test_wan_market_submission_has_no_nested_model(self):
        generated = self.plugin.nodes.generated
        catalog = json.loads((ROOT / "models" / "catalog.json").read_text(encoding="utf-8"))
        op = next(x for x in catalog["operations"]
                  if x.get("docs_url", "").endswith("/wan/3-0-video-prime.md"))
        fake = SimpleNamespace(
            wait_for_task=lambda *a, **kw: SimpleNamespace(raw={}, urls=[], credits_consumed=0),
        )
        submissions = []
        def submit(model, payload, **kwargs):
            submissions.append((model, payload))
            return "offline-task"
        fake.create_task = submit
        with patch.object(generated, "make_client", return_value=fake):
            generated._market_execute(
                op, "wan/3-0-video-prime", "utility",
                {"prompt": "test", "audio": False, "duration": 10},
                payload_model="wan/3-0-video-prime",
            )
        self.assertEqual(len(submissions), 1)
        model, payload = submissions[0]
        self.assertEqual(model, "wan/3-0-video-prime")
        self.assertNotIn("model", payload)
        self.assertIs(payload["audio"], False)
        self.assertEqual(payload["duration"], 10)
        self.assertLessEqual(set(payload), set(op["parameter_hints"]))

    def test_suno_image_reference_disables_custom_mode_before_submission(self):
        generated = self.plugin.nodes.generated
        op = {"docs_url": "https://docs.kie.ai/suno-api/generate-music.md"}
        payload = {
            "image_urls": ["https://example.test/reference.png"],
            "custom_mode": True,
            "duration": 20,
            "style": "Cinematic",
            "title": "Example",
            "instrumental": True,
            "model": "V6_WILD",
            "prompt": "music",
        }
        normalized = generated._normalize_suno_music_payload(op, payload)
        self.assertFalse(normalized["custom_mode"])
        self.assertNotIn("duration", normalized)
        self.assertNotIn("style", normalized)
        self.assertNotIn("title", normalized)
        self.assertNotIn("instrumental", normalized)
        self.assertEqual(normalized["model"], "V6_WILD")
        self.assertEqual(normalized["prompt"], "music")
        self.assertEqual(normalized["image_urls"], ["https://example.test/reference.png"])

    def test_suno_text_only_custom_mode_is_preserved(self):
        generated = self.plugin.nodes.generated
        op = {"docs_url": "https://docs.kie.ai/suno-api/generate-music.md"}
        payload = {"prompt": "music", "custom_mode": True}
        normalized = generated._normalize_suno_music_payload(op, payload)
        self.assertTrue(normalized["custom_mode"])

    def test_topaz_payload_normalization_still_applies(self):
        generated = self.plugin.nodes.generated
        normalized = generated._normalize_topaz_video_payload(
            "topaz/video-upscale",
            {"video_url": " https://example.test/input.mp4 ", "upscale_factor": "2x"},
        )
        self.assertEqual(normalized["video_url"], "https://example.test/input.mp4")
        self.assertEqual(normalized["upscale_factor"], "2")

    def test_boolean_audio_schema_is_not_treated_as_media(self):
        generated = self.plugin.nodes.generated
        op = {
            "title": "Wan 3.0 - Video Prime",
            "endpoint": "/api/v1/jobs/createTask",
            "parameter_hints": {
                "audio": {"type": "boolean", "required": False, "default": True},
            },
        }
        inputs = generated._friendly_input_types(op, model="wan/3-0-video-prime")
        self.assertEqual(inputs["optional"]["audio"][0], "BOOLEAN")
        payload = generated._build_payload(None, op, {"audio": "false"}, model="wan/3-0-video-prime")
        self.assertIs(payload["audio"], False)

    def test_real_audio_field_without_boolean_schema_remains_media(self):
        generated = self.plugin.nodes.generated
        op = {
            "title": "Audio Input",
            "parameter_hints": {"audio": {"type": "object", "required": True}},
        }
        inputs = generated._friendly_input_types(op)
        self.assertEqual(inputs["required"]["audio"][0], "AUDIO")

    def test_bootstrap_exposes_more_than_transport_helpers(self):
        # 15 utility/advanced nodes + individual model/version nodes.
        self.assertGreaterEqual(len(self.plugin.NODE_CLASS_MAPPINGS), 29)

    def test_studio_nodes_are_registered(self):
        names = set(self.plugin.NODE_DISPLAY_NAME_MAPPINGS.values())
        self.assertIn("KIE • Camera Director", names)
        self.assertIn("KIE • Shot Sequence", names)
        self.assertIn("KIE • Kling 3.0 Omni Studio", names)
        self.assertIn("KIE • Seedance Studio", names)

    def test_kling_studio_has_director_controls(self):
        node = self.find("KIE • Kling 3.0 Omni Studio")
        self.assertEqual(node.CATEGORY, "KIE Next/Studio/Kling")
        inputs = node.INPUT_TYPES()
        self.assertIn("shot_mode", inputs["required"])
        self.assertIn("camera_direction", inputs["optional"])
        self.assertIn("shot_sequence_json", inputs["optional"])

    def test_seedance_studio_has_explicit_modes(self):
        node = self.find("KIE • Seedance Studio")
        modes = node.INPUT_TYPES()["required"]["generation_mode"][0]
        self.assertIn("first + last frame", modes)
        self.assertIn("multimodal reference", modes)


if __name__ == "__main__":
    unittest.main()



def test_topaz_video_payload_normalization():
    payload = {"video_url": "  https://example.com/input.mp4  ", "upscale_factor": "2x"}
    normalized = generated._normalize_topaz_video_payload("topaz/video-upscale", payload)
    assert normalized["video_url"] == "https://example.com/input.mp4"
    assert normalized["upscale_factor"] == "2"


def test_topaz_video_payload_rejects_invalid_scale():
    try:
        generated._normalize_topaz_video_payload(
            "topaz/video-upscale",
            {"video_url": "https://example.com/input.mp4", "upscale_factor": "3"},
        )
    except generated.KIEAPIError as exc:
        assert "must be 1, 2, or 4" in str(exc)
    else:
        raise AssertionError("invalid Topaz upscale factor should fail before submission")


def test_topaz_retry_signature_is_narrow():
    assert generated._retryable_topaz_internal_error(generated.KIEAPIError("internal error, please try again later"))
    assert not generated._retryable_topaz_internal_error(generated.KIEAPIError("insufficient credits"))
