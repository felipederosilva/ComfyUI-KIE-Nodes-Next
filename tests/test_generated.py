import importlib.util
import pathlib
import sys
import unittest

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

