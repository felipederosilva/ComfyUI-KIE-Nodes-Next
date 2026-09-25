import unittest
from unittest.mock import patch

import torch

from test_generated import load_plugin


class TestConsistencyBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes.consistency_board import build_consistency_board, KIEPersistentPreviewImageNode
        cls.build = staticmethod(build_consistency_board)
        cls.preview = KIEPersistentPreviewImageNode

    def test_reference_and_variants_share_one_board_without_image_scoring(self):
        reference = torch.zeros((1, 30, 20, 3))
        reference[..., 0] = 1
        take = torch.zeros((1, 20, 30, 3))
        take[..., 1] = 1
        board = self.build(reference, [("Front", take), ("Profile", reference)])
        self.assertEqual(tuple(board.shape), (1, 390, 900, 3))
        self.assertGreater(float(board[0, 100, 150, 0]), .95)
        self.assertGreater(float(board[0, 100, 450, 1]), .95)
        self.assertNotIn("score", self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Consistency_Board"].RETURN_NAMES)

    def test_node_persists_preview_and_rejects_batch(self):
        frame = torch.zeros((1, 8, 8, 3))
        records = [{"filename": "Comparison.png", "type": "output", "subfolder": "KIE-Consistency"}]
        with patch.object(self.preview, "save_images", return_value={
            "ui": {"images": records, "kie_persistent_preview": records},
            "result": (None, "saved-files-json")}) as save:
            result = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Consistency_Board"]().compare(frame, frame)
        self.assertEqual(result["result"][1], "saved-files-json")
        self.assertEqual(result["ui"]["kie_persistent_preview"], records)
        self.assertIn("KIE-Consistency", save.call_args.args[1])
        with self.assertRaisesRegex(ValueError, "one RGB"):
            self.build(frame, [("Batch", torch.zeros((2, 8, 8, 3)))])


if __name__ == "__main__":
    unittest.main()
