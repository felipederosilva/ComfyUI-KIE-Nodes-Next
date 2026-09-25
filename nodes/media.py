from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from ..kie.helpers import make_client
from ..kie.media import (
    download_image_tensor,
    download_to_temp_file,
    download_video_object,
    upload_audio,
    upload_image_batch,
    video_to_temp_file,
)
from ..kie.media_compat import media_file_options


class KIEUploadImageNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("first_url", "urls_json")
    FUNCTION = "upload"
    CATEGORY = "KIE Next/Utility/Media"

    def upload(self, image, config=None):
        import json
        urls = upload_image_batch(make_client(config), image, prefix="comfy")
        return (urls[0], json.dumps(urls, ensure_ascii=False))


class KIEUploadVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("VIDEO",)}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "upload"
    CATEGORY = "KIE Next/Utility/Media"

    def upload(self, video, config=None):
        path = video_to_temp_file(video)
        url = make_client(config).upload_file(path, upload_path="comfyui/videos")
        return (url,)


class KIEUploadAudioNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audio": ("AUDIO",)}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "upload"
    CATEGORY = "KIE Next/Utility/Media"

    def upload(self, audio, config=None):
        return (upload_audio(make_client(config), audio, prefix="comfy"),)


class KIEUploadFilePathNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "local_path": ("STRING", {"default": "", "multiline": False}),
                "upload_path": ("STRING", {"default": "comfyui/uploads", "multiline": False}),
            },
            "optional": {"config": ("KIE_CONFIG",)},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("url",)
    FUNCTION = "upload"
    CATEGORY = "KIE Next/Utility/Media"
    DESCRIPTION = "Uploads an arbitrary local file to KIE. Useful for file/audio/API families not represented by a native Comfy media type."

    def upload(self, local_path, upload_path, config=None):
        import os
        path = os.path.abspath(os.path.expanduser(local_path.strip()))
        if not os.path.isfile(path):
            raise ValueError(f"File does not exist: {path}")
        return (make_client(config).upload_file(path, upload_path=upload_path.strip() or "comfyui/uploads"),)


class KIEDownloadImageNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"url": ("STRING", {"default": ""})}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "download"
    CATEGORY = "KIE Next/Utility/Media"

    def download(self, url, config=None):
        return (download_image_tensor(make_client(config), url.strip()),)


class KIEDownloadVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"url": ("STRING", {"default": ""})}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    FUNCTION = "download"
    CATEGORY = "KIE Next/Utility/Media"

    def download(self, url, config=None):
        return (download_video_object(make_client(config), url.strip()),)


class KIEDownloadFileNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"url": ("STRING", {"default": ""}), "suffix": ("STRING", {"default": ""})},
            "optional": {"config": ("KIE_CONFIG",)},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("local_path",)
    FUNCTION = "download"
    CATEGORY = "KIE Next/Utility/Media"

    def download(self, url, suffix, config=None):
        return (download_to_temp_file(make_client(config), url.strip(), suffix.strip()),)


class KIEPersistentPreviewImageNode:
    """A Preview Image replacement whose image record survives workflow reloads."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Images to save and display persistently."}),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "KIE-Previews/KIE",
                        "tooltip": "Saved below ComfyUI's output directory. Use a subfolder/prefix to organize previews.",
                    },
                ),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "saved_files_json")
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "KIE Next/Utility/Media"
    DESCRIPTION = (
        "Persistent alternative to ComfyUI Preview Image. Saves the images to output and stores "
        "their output-file reference in the workflow so the preview can be restored after reopening."
    )

    def save_images(self, images, filename_prefix="KIE-Previews/KIE", prompt=None, extra_pnginfo=None):
        try:
            from nodes import SaveImage  # type: ignore
        except Exception as exc:
            raise RuntimeError("KIE Persistent Preview Image requires ComfyUI's SaveImage node.") from exc

        saver = SaveImage()
        result = saver.save_images(images, filename_prefix, prompt, extra_pnginfo)
        records = list((result.get("ui") or {}).get("images") or [])
        return {
            "ui": {"images": records, "kie_persistent_preview": records},
            "result": (images, json.dumps(records, ensure_ascii=False)),
        }


def _save_video_output(video, filename_prefix: str) -> dict:
    """Save a VIDEO in Comfy output and return its durable /view descriptor."""
    try:
        import folder_paths  # type: ignore
    except Exception as exc:
        raise RuntimeError("KIE video output requires ComfyUI's folder_paths module.") from exc
    if video is None or not callable(getattr(video, "save_to", None)):
        raise ValueError("Connect a ComfyUI VIDEO object to preview or save it.")
    prefix = str(filename_prefix or "").strip()
    if not prefix:
        raise ValueError("Video filename prefix cannot be empty.")

    output_root = Path(folder_paths.get_output_directory()).resolve()
    try:
        width, height = video.get_dimensions()
    except Exception:
        width, height = 0, 0
    folder, basename, counter, subfolder, _ = folder_paths.get_save_image_path(
        prefix, str(output_root), width, height
    )
    directory = Path(folder).resolve()
    if not directory.is_relative_to(output_root):
        raise ValueError("Video output must stay inside the ComfyUI output directory.")
    if not basename or basename in {".", ".."}:
        raise ValueError("Invalid video filename prefix.")
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{basename}_{counter:05}_{uuid.uuid4().hex[:8]}.mp4"
    destination = directory / filename
    partial = directory / f".{filename}.{uuid.uuid4().hex}.partial.mp4"
    try:
        video.save_to(str(partial))
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError("ComfyUI produced an empty video file.")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)

    relative = destination.relative_to(output_root).as_posix()
    record = {"filename": filename, "subfolder": str(subfolder).replace("\\", "/"), "type": "output"}
    return {
        "ui": {
            "images": [record], "animated": [True],
            "videos": [record], "kie_persistent_video": record,
        },
        "result": (video, f"{relative} [output]"),
    }


class KIEPreviewVideoNode:
    """Playable preview with a durable asset reference after workflow reload."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("VIDEO",)}}

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "saved_file")
    FUNCTION = "preview"
    OUTPUT_NODE = True
    CATEGORY = "KIE Next/Utility/Media"
    DESCRIPTION = "Preview VIDEO in the graph. Keeps its file under output/KIE-Previews so the player survives reopening the workflow."

    def preview(self, video):
        return _save_video_output(video, "KIE-Previews/KIE")


class KIESaveVideoNode:
    """Export a VIDEO and make its saved file reusable in later workflows."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "video": ("VIDEO",),
            "filename_prefix": ("STRING", {"default": "KIE-Videos/KIE", "multiline": False}),
        }}

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "saved_file")
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "KIE Next/Utility/Media"
    DESCRIPTION = "Save VIDEO as MP4 under ComfyUI output and show a playable preview. The saved_file output works with Persistent Load Video."

    def save(self, video, filename_prefix="KIE-Videos/KIE"):
        return _save_video_output(video, filename_prefix)


class KIEPersistentLoadVideoNode:
    """Load an input or output video through a durable workflow widget."""

    @classmethod
    def INPUT_TYPES(cls):
        try:
            import folder_paths  # type: ignore
            files = media_file_options(folder_paths, ["video"])
        except Exception:
            files = []
        return {
            "required": {
                "file": (
                    files,
                    {
                        "tooltip": "Select a video from input or a saved ComfyUI output. Output values remain valid after restart.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "saved_file")
    FUNCTION = "load_video"
    CATEGORY = "KIE Next/Utility/Media"
    DESCRIPTION = (
        "Persistent replacement for Load Video. It directly supports nested input files and annotated output files "
        "such as V6_00001_.mp4 [output], and remembers the selection in the workflow."
    )

    def load_video(self, file):
        try:
            import folder_paths  # type: ignore
            from comfy_api.latest import InputImpl  # type: ignore
        except Exception as exc:
            raise RuntimeError("KIE Persistent Load Video requires a current ComfyUI video runtime.") from exc

        if not isinstance(file, str) or not file.strip() or not folder_paths.exists_annotated_filepath(file):
            raise ValueError(f"Video file is missing or unavailable: {file!r}")

        name, base_dir = folder_paths.annotated_filepath(file)
        media_type = "output" if base_dir and os.path.normcase(os.path.realpath(base_dir)) == os.path.normcase(os.path.realpath(folder_paths.get_output_directory())) else "input"
        subfolder, _, filename = name.replace("\\", "/").rpartition("/")
        record = {"filename": filename, "subfolder": subfolder, "type": media_type}
        return {
            "ui": {"videos": [record], "kie_persistent_video": record},
            "result": (InputImpl.VideoFromFile(folder_paths.get_annotated_filepath(file)), file),
        }

