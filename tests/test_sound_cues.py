import json
import unittest

from test_generated import load_plugin


class SoundCueSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.sound_cues import sound_cue_sheet
        cls.sound_cue_sheet = staticmethod(sound_cue_sheet)

    def setUp(self):
        self.timeline = json.dumps({"duration_seconds": 8, "events": [
            {"time_seconds": 0, "type": "start"},
            {"time_seconds": 3, "type": "visual_cut_candidate"}]})

    def test_only_editor_description_becomes_sfx(self):
        data, brief = self.sound_cue_sheet(self.timeline, '[{"time_seconds": 4, "description": "glass settles"}]',
                                      "quiet cafe", True)
        parsed = json.loads(data)
        self.assertEqual(parsed["cues"][0]["description"], "glass settles")
        self.assertEqual(parsed["visual_markers_to_review"][0]["time_seconds"], 3)
        self.assertEqual(len(parsed["cues"]), 1)
        self.assertIn("dialogue clear", brief)

    def test_visual_marker_does_not_invent_effect(self):
        data, brief = self.sound_cue_sheet(self.timeline, "", "silence", False)
        self.assertEqual(json.loads(data)["cues"], [])
        self.assertIn("No timed effects are approved", brief)

    def test_rejects_out_of_range_cue(self):
        with self.assertRaises(ValueError):
            self.sound_cue_sheet(self.timeline, '[{"time_seconds": 10, "description": "impact"}]', "room", True)
