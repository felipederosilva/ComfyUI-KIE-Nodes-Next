import json
import unittest

from test_generated import load_plugin


class TestVariations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_one_change_per_take_with_common_constraints(self):
        result = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Variation_Matrix"]().build(
            "Mara opens the door", "wide shot", "same face, coat, and room", "close-up", "low angle")
        manifest = json.loads(result[4])
        self.assertEqual(len(manifest["takes"]), 3)
        for index, prompt in enumerate(result[:3], 1):
            self.assertIn("Mara opens the door", prompt)
            self.assertIn("same face, coat, and room", prompt)
            self.assertIn(f"Change for take {index} only", prompt)
        self.assertEqual(result[3], "")
        with self.assertRaisesRegex(ValueError, "base prompt"):
            self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Variation_Matrix"]().build("", "wide")


if __name__ == "__main__":
    unittest.main()
