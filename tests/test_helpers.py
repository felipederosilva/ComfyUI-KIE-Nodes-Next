import unittest

from kie.helpers import apply_path_params, replace_placeholders


class TestHelpers(unittest.TestCase):
    def test_path_params_are_url_encoded(self):
        self.assertEqual(apply_path_params("/api/task/{taskId}/file/:name", {"taskId": "a/b", "name": "x y"}), "/api/task/a%2Fb/file/x%20y")

    def test_recursive_placeholders(self):
        source = {"images": "$image_urls", "nested": {"video": "$video_url"}, "leave": "prefix $video_url"}
        out = replace_placeholders(source, {"$image_urls": ["a", "b"], "$video_url": "v"})
        self.assertEqual(out["images"], ["a", "b"])
        self.assertEqual(out["nested"]["video"], "v")
        self.assertEqual(out["leave"], "prefix $video_url")


if __name__ == "__main__":
    unittest.main()

