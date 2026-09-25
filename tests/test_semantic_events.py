import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from test_generated import load_plugin


class SemanticEventsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.semantic_events import sample_video_file, frame_contact_sheet, reviewed_event_timeline
        from kie_next_testpkg.nodes.video_events import music_brief
        from kie_next_testpkg.nodes.sound_cues import sound_cue_sheet
        cls.sample_video_file = staticmethod(sample_video_file)
        cls.frame_contact_sheet = staticmethod(frame_contact_sheet)
        cls.reviewed_event_timeline = staticmethod(reviewed_event_timeline)
        cls.music_brief = staticmethod(music_brief)
        cls.sound_cue_sheet = staticmethod(sound_cue_sheet)

    def test_sparse_frames_are_timecoded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "sample.avi")
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 4, (64, 64))
            self.assertTrue(writer.isOpened())
            for index in range(8):
                writer.write(np.full((64, 64, 3), 20 if index < 4 else 230, dtype=np.uint8))
            writer.release()
            frames, times_json = self.sample_video_file(path, 4)
        self.assertEqual(tuple(frames.shape), (4, 288, 512, 3))
        record = json.loads(times_json)
        self.assertEqual(len(record["sampled_seconds"]), 4)
        self.assertAlmostEqual(record["duration_seconds"], 2.0, places=1)
        sheet = self.frame_contact_sheet(frames, times_json)
        self.assertEqual(tuple(sheet.shape), (1, 630, 1024, 3))

    def test_human_review_gates_semantic_music_and_sound(self):
        frame_times = json.dumps({"duration_seconds": 8, "sampled_seconds": [0, 4, 7]})
        events = json.dumps({"events": [{"time_seconds": 4, "description": "door visibly closes"}]})
        with self.assertRaisesRegex(ValueError, "enable editor_reviewed"):
            self.reviewed_event_timeline(frame_times, events, False)
        reviewed = self.reviewed_event_timeline(frame_times, events, True)
        prompt, _, music_sheet = self.music_brief(reviewed, "tense", "ambient", 90)
        sound_json, sound_brief = self.sound_cue_sheet(reviewed, "", "quiet hall", True)
        self.assertIn("door visibly closes", prompt)
        self.assertEqual(json.loads(music_sheet)["source"], "editor-reviewed vision notes")
        self.assertEqual(json.loads(sound_json)["cues"][0]["description"], "door visibly closes")
        self.assertIn("door visibly closes", sound_brief)
        with self.assertRaisesRegex(ValueError, "valid time"):
            self.reviewed_event_timeline(frame_times,
                json.dumps({"events": [{"time_seconds": 9, "description": "late"}]}), True)
