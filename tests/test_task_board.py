import json
import unittest
from unittest.mock import patch

from test_generated import load_plugin


class TaskBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.task_board import task_board
        cls.task_board = staticmethod(task_board)

    def test_multiple_read_only_statuses_and_failure(self):
        class Client:
            def __init__(self): self.calls = []
            def get_task(self, task_id):
                self.calls.append(task_id)
                if task_id == "A":
                    return {"state": "success", "progress": 100,
                            "resultJson": '{"resultUrls":["https://example.test/output.mp4"]}',
                            "creditsConsumed": 12}
                if task_id == "B":
                    return {"state": "fail", "failMsg": "provider rejected input"}
                raise RuntimeError("unreachable")
        client = Client()
        data, summary = self.task_board(client, "A, B\nA, C")
        rows = json.loads(data)["tasks"]
        self.assertEqual(client.calls, ["A", "B", "C"])
        self.assertEqual(rows[0]["result_urls"], ["https://example.test/output.mp4"])
        self.assertEqual(rows[1]["failure"], "provider rejected input")
        self.assertEqual(rows[2]["state"], "lookup_error")
        self.assertIn("A: success", summary)

    def test_requires_finite_watchlist(self):
        from kie_next_testpkg.nodes import task_board as module
        with patch.object(module, "recent_tasks", return_value=[]):
            with self.assertRaises(ValueError):
                self.task_board(object(), "")
