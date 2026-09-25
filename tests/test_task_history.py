import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_generated import load_plugin


class TaskHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.kie import task_history
        cls.history = task_history

    def test_submitted_then_success_and_no_secret_fields(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(self.history, "_path", return_value=Path(folder) / "tasks.json"):
            self.history.record_task("t-1", "wan/video", "submitted")
            self.history.record_task("t-1", "wan/video", "success", credits=12)
            self.history.record_task("t-2", "suno", "submitted")
            rows = self.history.recent_tasks()
            self.assertEqual([row["task_id"] for row in rows], ["t-2", "t-1"])
            self.assertEqual(rows[1]["credits_consumed"], 12)
            self.assertNotIn("api_key", str(rows).lower())
            self.assertNotIn("prompt", str(rows).lower())
