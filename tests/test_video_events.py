import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from test_generated import load_plugin


class TestVideoEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes.video_events import analyze_video_file, music_brief
        cls.analyze_file = staticmethod(analyze_video_file)
        cls.music_brief = staticmethod(music_brief)

    def test_detects_timed_visual_change_without_claiming_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "two_scenes.avi")
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 64))
            self.assertTrue(writer.isOpened())
            try:
                for frame in range(30):
                    value = 10 if frame < 15 else 240
                    writer.write(np.full((64, 64, 3), value, dtype=np.uint8))
            finally:
                writer.release()
            data = self.analyze_file(path, sample_interval=0.5)
        cuts = [e for e in data["events"] if e["type"] == "visual_cut_candidate"]
        self.assertTrue(any(abs(e["time_seconds"] - 1.5) <= 0.5 for e in cuts))
        self.assertIn("Pixel-change", data["interpretation"])

    def test_editor_story_cues_replace_unverified_semantic_guess(self):
        timeline = {"duration_seconds": 12, "events": [
            {"time_seconds": 0, "type": "start"},
            {"time_seconds": 4, "type": "visual_cut_candidate"}]}
        prompt, style, sheet = self.music_brief(json.dumps(timeline), "warm", "piano", 92,
                                                 '[{"time_seconds":4,"description":"The letter is opened"}]')
        self.assertIn("The letter is opened", prompt)
        self.assertIn("No vocals", prompt)
        self.assertEqual(style, "piano")
        self.assertEqual(json.loads(sheet)["source"], "editor annotations")
        node = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Music_Brief"]()
        outputs = node.build(json.dumps(timeline), "warm", "piano", 92)
        self.assertEqual(outputs[2:4], (False, True))
        with self.assertRaisesRegex(ValueError, "within the video"):
            self.music_brief(json.dumps(timeline), "warm", "piano", 92,
                             '[{"time_seconds":20,"description":"Late event"}]')


if __name__ == "__main__":
    unittest.main()
