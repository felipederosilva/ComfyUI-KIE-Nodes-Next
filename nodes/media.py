from __future__ import annotations

from ..kie.helpers import make_client
from ..kie.media import (
    download_image_tensor,
    download_to_temp_file,
    download_video_object,
    upload_audio,
    upload_image_batch,
    video_to_temp_file,
)


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

