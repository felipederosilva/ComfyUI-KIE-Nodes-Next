import json
import unittest
from unittest.mock import patch

from test_generated import load_plugin


class TestCameraPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes.camera_path import build_camera_path, KIEPersistentPreviewImageNode
        cls.build_path = staticmethod(build_camera_path)
        cls.preview = KIEPersistentPreviewImageNode

    def test_orbit_keyframes_and_preview_are_consistent(self):
        plan, image, direction = self.build_path("orbit", 4, "linear", (0, 1.5, -4),
                                                 (0, 1.5, 0), (0, 1.5, -4), (0, 1.5, 0), 90, 5)
        self.assertEqual(len(plan["keyframes"]), 5)
        self.assertEqual(plan["keyframes"][0]["time_seconds"], 0)
        self.assertEqual(plan["keyframes"][-1]["time_seconds"], 4)
        self.assertAlmostEqual(plan["keyframes"][0]["position"][2], -4, places=3)
        self.assertAlmostEqual(plan["keyframes"][-1]["position"][0], 4, places=3)
        self.assertEqual(tuple(image.shape), (1, 460, 640, 3))
        self.assertIn("editorial intent", direction)

    def test_node_saves_local_preview_and_rejects_invalid_duration(self):
        records = [{"filename": "Path.png", "type": "output", "subfolder": "KIE-Camera"}]
        with patch.object(self.preview, "save_images", return_value={
            "ui": {"images": records, "kie_persistent_preview": records}, "result": (None, "saved")}) as save:
            result = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Camera_Path"]().plan(
                "dolly", 5, "linear", 0, 1.6, -4, 0, 1.6, -2, 0, 1.6, 0)
        self.assertEqual(result["ui"]["kie_persistent_preview"], records)
        self.assertEqual(json.loads(result["result"][1])["mode"], "dolly")
        save.assert_called_once()
        with self.assertRaisesRegex(ValueError, "outside"):
            self.build_path("dolly", 0, "linear", (0, 0, 0), (0, 0, 0), (1, 1, 1), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
