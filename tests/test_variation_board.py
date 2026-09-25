import json
import unittest

import torch

from test_generated import load_plugin


class VariationBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.variation_board import build_variation_board
        cls.build_variation_board = staticmethod(build_variation_board)

    def test_two_takes_render_with_edit_deltas(self):
        matrix = json.dumps({"takes": [{"take": 1, "delta": "wide shot"},
                                        {"take": 2, "delta": "close-up"}]})
        image = torch.zeros(1, 48, 64, 3)
        board, report = self.build_variation_board(matrix, [(1, image), (2, image + 0.5)])
        self.assertEqual(tuple(board.shape), (1, 355, 720, 3))
        self.assertEqual(json.loads(report)["compared"][1]["delta"], "close-up")

    def test_rejects_undefined_take_and_missing_images(self):
        matrix = json.dumps({"takes": [{"take": 1, "delta": "wide"}]})
        with self.assertRaisesRegex(ValueError, "not defined"):
            self.build_variation_board(matrix, [(2, torch.zeros(1, 20, 20, 3))])
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.build_variation_board(matrix, [])
