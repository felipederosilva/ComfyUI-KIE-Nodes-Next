import unittest

from test_generated import load_plugin


MARKET = "/api/v1/jobs/createTask"


class TestNovemberModelControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = load_plugin().nodes.generated

    def operation(self, **hints):
        return {"endpoint": MARKET, "parameter_hints": hints}

    def payload(self, model, op, **kwargs):
        return self.generated._build_payload(None, op, kwargs, model=model, dry_run=True)

    def report(self, model, op, **kwargs):
        return self.generated.preflight_model_inputs(op, model, kwargs)

    def test_image_26_uses_only_the_selected_formats_fields(self):
        op = self.operation(
            output_format={"type": "string", "enum": ["png", "gif", "svg"]},
            size={"type": "string"}, frame_count={"type": "integer"},
            frame_duration_ms={"type": "integer"}, resolution={"type": "string"},
            aspect_ratio={"type": "string"}, output_compression={"type": "integer"},
            svg={"type": "object", "properties": {"model": {
                "type": "string", "enum": ["gpt-6-sol", "gpt-5.6-luna"], "default": "gpt-5.6-luna",
            }}},
        )
        model = "gpt-image-2-6/flare-text-to-image"
        fields = self.generated._friendly_input_types(op, model=model)["optional"]
        self.assertEqual(fields["frame_duration_ms"][1]["step"], 10)
        self.assertEqual(fields["svg_model"][1]["default"], "gpt-5.6-luna")
        self.assertNotIn("svg", fields)
        common = dict(size="768x768", frame_count=12, frame_duration_ms=200, resolution="2K",
                      aspect_ratio="16:9", output_compression=75, svg_model="gpt-6-sol")
        self.assertEqual(self.payload(model, op, output_format="png", **common),
                         {"output_format": "png", "resolution": "2K", "aspect_ratio": "16:9"})
        self.assertEqual(self.payload(model, op, output_format="gif", **common),
                         {"output_format": "gif", "size": "768x768", "frame_count": 12, "frame_duration_ms": 200})
        self.assertEqual(self.payload(model, op, output_format="svg", **common)["svg"], {"model": "gpt-6-sol"})
        common["frame_count"] = 16
        self.assertIn("sprite sheet", str(self.report(model, op, output_format="gif", **common)["errors"]))

    def test_image_26_economy_keeps_gif_aspect_ratio_and_omits_automatic_duration(self):
        model = "gpt-image-2-6/economy-text-to-image"
        op = self.operation(output_format={"type": "string"}, aspect_ratio={"type": "string"},
                            frame_duration_ms={"type": "number"}, frame_count={"type": "string"})
        payload = self.payload(model, op, output_format="gif", aspect_ratio="16:9",
                               frame_count="auto", frame_duration_ms=0)
        self.assertEqual(payload, {"output_format": "gif", "aspect_ratio": "16:9", "frame_count": "auto"})

    def test_image_26_documentation_url_examples_are_not_submitted_by_default(self):
        op = self.operation(mask_url={"type": "string", "default": "https://example.com/mask.png"},
                            markup={"type": "string", "default": "https://example.com/markup.png"})
        model = "gpt-image-2-6/flare-image-to-image"
        widgets = self.generated._friendly_input_types(op, model=model)["optional"]
        for name in ("mask_url", "markup"):
            self.assertEqual(widgets[name][1]["default"], "")
        self.assertFalse(self.report(model, op, mask_url="https://example.test/mask.png",
                                     markup="https://example.test/mark.png")["valid"])

    def test_seedance_flash_omits_reference_mode_default_and_roundtrips_auto_duration(self):
        model = "bytedance/seedance-2-5-flash"
        op = self.operation(prompt={"type": "string"}, duration={"type": "integer"},
                            omni_reference_task_type={"type": "string", "enum": ["auto", "reference", "edit", "extend"]},
                            aspect_ratio={"type": "string"}, first_frame_url={"type": "string"},
                            reference_video_urls={"type": "array", "maxItems": 5})
        widgets = self.generated._friendly_input_types(op, model=model)["optional"]
        self.assertIn("reference_video_5", widgets)
        self.assertNotIn("0", widgets["duration"][0])
        mode_default = widgets["omni_reference_task_type"][1]["default"]
        payload = self.payload(model, op, duration="-1", prompt="A tracked shot", omni_reference_task_type=mode_default)
        self.assertEqual(payload, {"duration": -1, "prompt": "A tracked shot"})
        self.assertTrue(self.report(model, op, omni_reference_task_type="edit", duration="-1",
                                    aspect_ratio="adaptive", reference_video_1=object())["valid"])
        invalid = self.report(model, op, omni_reference_task_type="edit", duration="5",
                              aspect_ratio="16:9", first_frame_url=object())
        self.assertIn("requires a reference video", str(invalid["errors"]))
        self.assertIn("requires automatic duration", str(invalid["errors"]))

    def test_kling_long_image_has_separate_native_references_for_web_and_product(self):
        model = "kling-4-0/long-image"
        op = self.operation(prompt={"type": "string"}, image_urls={"type": "array", "maxItems": 3},
                            style_image={"type": "string"}, subject_image={"type": "string"},
                            length={"type": "string"}, skill={"type": "string"})
        widgets = self.generated._friendly_input_types(op, model=model)["optional"]
        self.assertEqual(widgets["style_image"][0], "IMAGE")
        self.assertEqual(widgets["subject_image"][0], "IMAGE")
        self.assertNotIn("length", self.payload(model, op, skill="webpage", length="long"))
        self.assertTrue(self.report(model, op, skill="webpage", prompt="Use @style", style_image=object())["valid"])
        self.assertFalse(self.report(model, op, skill="ecommerce", prompt="Use @image_1")["valid"])
        self.assertFalse(self.report(model, op, skill="webpage", image_urls=object())["valid"])

    def test_kling_series_count_and_mention_checks(self):
        model = "kling-4-0/image"
        op = self.operation(prompt={"type": "string"}, mode={"type": "string"}, count={"type": "integer"},
                            image_urls={"type": "array", "maxItems": 10}, elements={"type": "array"})
        valid = self.report(model, op, prompt="Morning and dusk with @image_1", mode="series",
                            count=2, image_urls=object())
        self.assertTrue(valid["valid"])
        invalid = self.report(model, op, prompt="Missing @image_1", mode="series", count=1)
        self.assertIn("2–10", str(invalid["errors"]))
        self.assertIn("@image_1", str(invalid["errors"]))

    def test_minimax_exact_dimensions_exclude_tier_and_ratio(self):
        model = "minimax-h3/image-edit"
        op = self.operation(resolution={"type": "string"}, aspect_ratio={"type": "string"},
                            width={"type": "integer", "minimum": 1, "maximum": 8192},
                            height={"type": "integer", "minimum": 1, "maximum": 8192})
        fields = self.generated._friendly_input_types(op, model=model)["optional"]
        self.assertEqual(fields["width"][1]["default"], 0)
        self.assertEqual(self.payload(model, op, resolution="2K", aspect_ratio="auto", width=1920, height=1080),
                         {"width": 1920, "height": 1080})
        self.assertEqual(self.payload(model, op, resolution="2K", width=0, height=0), {"resolution": "2K"})
        self.assertFalse(self.report(model, op, width=100, height=40)["valid"])
        self.assertFalse(self.report(model, op, width=1920, height=0)["valid"])

    def test_seedream_transparency_requires_png(self):
        model = "seedream/5-5-image-to-image"
        op = self.operation(background={"type": "string"}, output_format={"type": "string"})
        self.assertFalse(self.report(model, op, output_format="jpeg", background="transparent")["valid"])
        self.assertTrue(self.report(model, op, output_format="png", background="transparent")["valid"])

    def test_omni_12_selects_native_video_edit_and_preserves_legacy_widgets(self):
        model = "google/gemini-omni-flash-1-2"
        op = self.operation(video_list={"type": "array", "maxItems": 1},
                            duration={"type": "integer"}, first_frame_url={"type": "string"},
                            last_frame_url={"type": "string"}, character_ids={
                                "type": "array", "default": ["example-id"], "maxItems": 2,
                            })
        widgets = self.generated._friendly_input_types(op, model=model)["optional"]
        self.assertEqual(widgets["video_1"][0], "VIDEO")
        self.assertNotIn("video_2", widgets)
        self.assertEqual(widgets["character_ids"][1]["default"], "[]")
        previous = self.generated._friendly_input_types(op, model="google/gemini-omni-flash-1-1")["optional"]
        self.assertEqual(previous["video_list"][0], "STRING")
        payload = self.payload(model, op, video_1=object(), duration=8, character_ids="[]")
        self.assertEqual(payload, {"video_list": ["https://preflight.invalid/video_1"]})
        self.assertFalse(self.report(model, op, video_1=object(), first_frame_url=object())["valid"])
        self.assertFalse(self.report(model, op, duration=12, first_frame_url=object(), last_frame_url=object())["valid"])

    def test_ltx_fast_higher_fps_and_resolution_limit_duration(self):
        op = self.operation(duration={"type": "integer"}, fps={"type": "integer"}, resolution={"type": "string"})
        model = "ltx/2-5-fast-text-to-video"
        for kwargs in (dict(duration=12, fps=50), dict(duration=12, resolution="1440p")):
            self.assertFalse(self.report(model, op, **kwargs)["valid"])
        self.assertTrue(self.report(model, op, duration=20, fps=24, resolution="1080p")["valid"])
        audio = self.operation(duration={"type": "number", "minimum": 2, "maximum": 20})
        model = "ltx/2-5-fast-audio-to-video"
        self.assertEqual(self.payload(model, audio, duration=0.0), {})
        self.assertEqual(self.payload(model, audio, duration=2.5), {"duration": 2.5})

    def test_nemotron_defaults_to_transcription_and_rejects_timestamps_with_translation(self):
        op = self.operation(timestamps={"type": "boolean"}, target_language={"type": "string", "enum": ["en", "pt"]})
        model = "nvidia/nemotron-3-5-transcribe"
        widgets = self.generated._friendly_input_types(op, model=model)["optional"]
        default_language = widgets["target_language"][1]["default"]
        self.assertEqual(self.payload(model, op, timestamps=True, target_language=default_language), {"timestamps": True})
        self.assertFalse(self.report(model, op, timestamps=True, target_language="pt")["valid"])


if __name__ == "__main__":
    unittest.main()
