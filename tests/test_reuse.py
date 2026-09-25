import json
import unittest
from unittest.mock import Mock, patch

from test_generated import load_plugin


class TestReuse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes import reuse
        cls.reuse = reuse

    def test_recovers_second_result_without_submitting_or_counting_again(self):
        client = Mock()
        client.get_task.return_value = {"state": "success", "taskId": "task-42",
                                        "creditsConsumed": 8.5,
                                        "resultJson": json.dumps({"resultUrls": [
                                            "https://result.example/one.mp4", "https://result.example/two.mp4"]}),
                                        "paramJson": '{"input":"https://source.example/input.mp4"}'}
        with patch.object(self.reuse, "make_client", return_value=client), patch.object(
                self.reuse, "download_video_object", return_value="persistent-video") as download:
            output = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Reuse_Completed_Video"]().reuse("task-42", 1)
        self.assertEqual(output[0], "persistent-video")
        self.assertEqual(output[1], "https://result.example/two.mp4")
        self.assertEqual(output[4], 8.5)
        self.assertNotIn("source.example", output[3])
        client.get_task.assert_called_once_with("task-42")
        client.create_task.assert_not_called()
        download.assert_called_once()

    def test_rejects_unfinished_task_without_downloading(self):
        client = Mock()
        client.get_task.return_value = {"state": "processing"}
        with patch.object(self.reuse, "make_client", return_value=client), patch.object(
                self.reuse, "download_image_tensor") as download:
            with self.assertRaisesRegex(ValueError, "processing"):
                self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Reuse_Completed_Image"]().reuse("task-4")
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
