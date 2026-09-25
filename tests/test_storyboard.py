import json
import unittest
from unittest.mock import patch

import torch

from test_generated import load_plugin


class TestStoryboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes.storyboard import build_storyboard
        cls.build_storyboard = staticmethod(build_storyboard)

    def test_contact_sheet_keeps_shot_order_and_hero_frame(self):
        shots = [{"prompt": "Wide city", "duration": 3, "camera": {"movement": "dolly in"}},
                 {"prompt": "Close portrait", "duration": 4}]
        red = torch.zeros((1, 16, 16, 3))
        red[..., 0] = 1
        sheet, data = self.build_storyboard(json.dumps(shots), {1: red})
        self.assertEqual(tuple(sheet.shape), (1, 420, 1024, 3))
        self.assertEqual(data["total_duration"], 7)
        self.assertTrue(data["shots"][0]["hero_frame_connected"])
        self.assertFalse(data["shots"][1]["hero_frame_connected"])
        self.assertGreater(float(sheet[0, 150, 250, 0]), .9)
        self.assertEqual(self.plugin.NODE_DISPLAY_NAME_MAPPINGS["KIE_Next_Storyboard_Contact_Sheet"],
                         "KIE • Storyboard Contact Sheet")

    def test_rejects_misaligned_or_ambiguous_frames(self):
        shots = json.dumps([{"prompt": "First", "duration": 2}])
        with self.assertRaisesRegex(ValueError, "beyond"):
            self.build_storyboard(shots, {2: torch.zeros((1, 8, 8, 3))})
        with self.assertRaisesRegex(ValueError, "not an image batch"):
            self.build_storyboard(shots, {1: torch.zeros((2, 8, 8, 3))})

    def test_node_saves_persistent_preview_and_returns_editable_metadata(self):
        from kie_next_testpkg.nodes.storyboard import KIEPersistentPreviewImageNode
        record = {"filename": "Storyboard_00001.png", "subfolder": "KIE-Storyboards", "type": "output"}
        with patch.object(KIEPersistentPreviewImageNode, "save_images", return_value={
            "ui": {"images": [record], "kie_persistent_preview": [record]},
            "result": (None, json.dumps([record]))}):
            result = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Storyboard_Contact_Sheet"]().render(
                json.dumps([{"prompt": "Opening scene", "duration": 2}]))
        self.assertEqual(result["ui"]["kie_persistent_preview"], [record])
        self.assertEqual(json.loads(result["result"][1])["shots"][0]["prompt"], "Opening scene")


if __name__ == "__main__":
    unittest.main()
