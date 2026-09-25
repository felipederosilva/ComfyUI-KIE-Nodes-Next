import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from test_generated import load_plugin


class TestElements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes import elements
        cls.elements = elements

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(self.elements, "elements_root", return_value=Path(self.temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.image = torch.zeros((1, 12, 12, 3))
        self.image[..., 0] = 1

    def test_save_load_reference_and_immutable_version(self):
        saver = self.elements.KIESaveElementNode()
        saved, prompt = saver.save_element("location", "Old Station", "1", "Green tiled hall", self.image, "Keep the clock above the door")
        self.assertIn("Green tiled hall", prompt)
        again, _ = saver.save_element("location", "Old Station", "1", "Green tiled hall", self.image, "Keep the clock above the door")
        self.assertEqual(again["manifest"]["content_sha256"], saved["manifest"]["content_sha256"])
        label = "location · Old Station · v1"
        loaded, _ = self.elements.KIELoadElementNode().load_element(label)
        image, reference_prompt = self.elements.KIEElementReferenceNode().load_reference(loaded)
        self.assertEqual(tuple(image.shape), (1, 12, 12, 3))
        self.assertGreater(float(image[0, 0, 0, 0]), .99)
        self.assertIn("clock", reference_prompt)
        with self.assertRaisesRegex(ValueError, "new version"):
            saver.save_element("location", "Old Station", "1", "Blue tiled hall", self.image)

    def test_style_can_be_text_only_but_reference_cannot_be_faked(self):
        saved, prompt = self.elements.KIESaveElementNode().save_element("style", "Muted Film", "1", "Soft grain, cool shadows")
        self.assertIn("Soft grain", prompt)
        with self.assertRaisesRegex(ValueError, "no image"):
            self.elements.KIEElementReferenceNode().load_reference(saved)
        with self.assertRaisesRegex(ValueError, "needs one approved"):
            self.elements.KIESaveElementNode().save_element("prop", "Lamp", "1", "Brass lamp")

    def test_changed_image_fails_integrity_check(self):
        saved, _ = self.elements.KIESaveElementNode().save_element("prop", "Lamp", "1", "Brass lamp", self.image)
        (Path(saved["directory"]) / "reference.png").write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.elements.KIEElementReferenceNode().load_reference(saved)


if __name__ == "__main__":
    unittest.main()
