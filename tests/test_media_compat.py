from pathlib import Path

from kie.media_compat import media_file_options, recursive_input_files


def test_recursive_input_files_returns_nested_forward_slash_paths(tmp_path: Path):
    (tmp_path / "root.png").write_bytes(b"png")
    (tmp_path / "pasted").mkdir()
    (tmp_path / "pasted" / "image (11).png").write_bytes(b"png")
    (tmp_path / "pasted" / "clip.mp4").write_bytes(b"video")

    result = recursive_input_files(str(tmp_path), lambda name: name.lower().endswith(".png"))

    assert result == ["pasted/image (11).png", "root.png"]


def test_recursive_input_files_ignores_symlinked_directories(tmp_path: Path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "image.png").write_bytes(b"png")
    link = tmp_path / "linked"
    try:
        link.symlink_to(tmp_path / "real", target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    result = recursive_input_files(str(tmp_path), lambda name: name.endswith(".png"))

    assert result == ["real/image.png"]


def test_media_file_options_includes_durable_annotated_output(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    (input_dir / "pasted").mkdir(parents=True)
    output_dir.mkdir()
    (input_dir / "pasted" / "source.mp4").write_bytes(b"video")
    (output_dir / "V6_00001_.mp4").write_bytes(b"video")

    class FolderPaths:
        @staticmethod
        def get_input_directory():
            return str(input_dir)

        @staticmethod
        def get_output_directory():
            return str(output_dir)

        @staticmethod
        def filter_files_content_types(files, _types):
            return [file for file in files if file.endswith(".mp4")]

    assert media_file_options(FolderPaths, ["video"]) == [
        "pasted/source.mp4",
        "V6_00001_.mp4 [output]",
    ]
