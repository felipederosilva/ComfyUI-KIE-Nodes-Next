import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from test_generated import load_plugin


class TestCharacterVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes import characters, character_variants
        cls.characters, cls.variants = characters, character_variants

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for obj, name, value in ((self.characters, "character_packs_root", root / "characters"),
                                 (self.variants, "character_packs_root", root / "characters"),
                                 (self.variants, "variants_root", root / "variants")):
            patcher = patch.object(obj, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.image = torch.zeros((1, 10, 10, 3))
        self.image[..., 1] = 1
        self.pack, _ = self.characters.KIESaveCharacterPackNode().save_pack(
            "Mara", "1", "Short curly hair and green eyes", "cinematic realism", "Keep facial structure", portrait=self.image)

    def test_variant_is_versioned_child_and_loads_approved_image(self):
        saver = self.variants.KIESaveCharacterVariantNode()
        saved, prompt = saver.save_variant(self.pack, "Winter coat", "1", "Long red wool coat", self.image,
                                           "Exterior winter scenes")
        self.assertIn("Short curly hair", prompt)
        self.assertIn("red wool coat", prompt)
        same, _ = saver.save_variant(self.pack, "Winter coat", "1", "Long red wool coat", self.image,
                                     "Exterior winter scenes")
        self.assertEqual(saved["manifest"]["content_sha256"], same["manifest"]["content_sha256"])
        image, loaded_prompt, payload = self.variants.KIELoadCharacterVariantNode().load_variant(self.pack, "Winter coat", "1")
        self.assertEqual(tuple(image.shape), (1, 10, 10, 3))
        self.assertIn("Winter coat", loaded_prompt)
        self.assertEqual(payload["manifest"]["parent_content_sha256"], self.pack["manifest"]["content_sha256"])
        self.assertFalse((Path(self.pack["directory"]) / "variants").exists())
        with self.assertRaisesRegex(ValueError, "new version"):
            saver.save_variant(self.pack, "Winter coat", "1", "Blue wool coat", self.image)

    def test_cannot_load_changed_approved_image(self):
        saved, _ = self.variants.KIESaveCharacterVariantNode().save_variant(
            self.pack, "Workwear", "1", "Dark jacket", self.image)
        (Path(saved["directory"]) / "approved.png").write_bytes(b"not an image")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.variants.KIELoadCharacterVariantNode().load_variant(self.pack, "Workwear", "1")


if __name__ == "__main__":
    unittest.main()
