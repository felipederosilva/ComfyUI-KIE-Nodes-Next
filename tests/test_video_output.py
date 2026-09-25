import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_plugin():
    name = "kie_next_testpkg"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeVideo:
    def get_dimensions(self):
        return (1024, 576)

    def save_to(self, path):
        pathlib.Path(path).write_bytes(b"video-test-content")


class TestVideoOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = pathlib.Path(self.temp.name) / "output"
        self.output.mkdir()

        def save_path(prefix, output_root, width, height):
            self.assertEqual((width, height), (1024, 576))
            path = pathlib.Path(prefix.replace("\\", "/"))
            folder = pathlib.Path(output_root) / path.parent
            folder.mkdir(parents=True, exist_ok=True)
            return str(folder), path.name, 1, path.parent.as_posix(), prefix

        fake_folder_paths = types.SimpleNamespace(
            get_output_directory=lambda: str(self.output),
            get_save_image_path=save_path,
        )
        patcher = patch.dict(sys.modules, {"folder_paths": fake_folder_paths})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_preview_and_save_produce_playable_durable_output_records(self):
        video = FakeVideo()
        for node_id, folder in (
            ("KIE_Next_Preview_Video", "KIE-Previews"),
            ("KIE_Next_Save_Video", "KIE-Videos"),
        ):
            node = self.plugin.NODE_CLASS_MAPPINGS[node_id]()
            result = node.preview(video) if folder == "KIE-Previews" else node.save(video)
            self.assertIs(result["result"][0], video)
            saved_file = result["result"][1]
            self.assertTrue(saved_file.startswith(f"{folder}/KIE_"))
            self.assertTrue(saved_file.endswith(".mp4 [output]"))
            record = result["ui"]["kie_persistent_video"]
            self.assertEqual(record["type"], "output")
            self.assertEqual(record["subfolder"], folder)
            self.assertEqual(result["ui"]["animated"], [True])
            self.assertEqual((self.output / folder / record["filename"]).read_bytes(), b"video-test-content")

    def test_repeated_saves_do_not_overwrite_prior_video(self):
        node = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Save_Video"]()
        first = node.save(FakeVideo())["ui"]["kie_persistent_video"]["filename"]
        second = node.save(FakeVideo())["ui"]["kie_persistent_video"]["filename"]
        self.assertNotEqual(first, second)
        self.assertTrue((self.output / "KIE-Videos" / first).exists())
        self.assertTrue((self.output / "KIE-Videos" / second).exists())

    def test_rejects_non_video_without_writing(self):
        node = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Preview_Video"]()
        with self.assertRaisesRegex(ValueError, "VIDEO object"):
            node.preview(object())
        self.assertEqual(list(self.output.rglob("*.mp4")), [])


if __name__ == "__main__":
    unittest.main()
