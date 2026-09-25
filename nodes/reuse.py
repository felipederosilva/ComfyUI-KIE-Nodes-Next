"""Recover existing paid results by task ID without creating another task."""
from __future__ import annotations

import json

from ..kie.client import KIEAPIError, KIEClient
from ..kie.helpers import make_client
from ..kie.media import download_audio_object, download_image_tensor, download_video_object
from .generated import _preferred_urls


def _existing_result(client, task_id: str, kind: str, index: int):
    task_id = str(task_id or "").strip()
    if not task_id:
        raise ValueError("Paste a completed KIE task ID. Do not connect a generation node here if you want to reuse a frozen result.")
    data = client.get_task(task_id)
    state = str(data.get("state") or "").lower()
    if state != "success":
        raise ValueError(f"Task {task_id} is {state or 'unknown'}; only completed tasks can be reused.")
    urls = KIEClient.extract_result_urls(data)
    candidates = _preferred_urls(urls, kind)
    if not candidates:
        raise KIEAPIError("Completed task has no result URL yet. Retry retrieval of the same task ID; do not submit it again.", payload=data)
    if index < 0 or index >= len(candidates):
        raise ValueError(f"Result index {index} is unavailable; this task has {len(candidates)} {kind} candidate(s).")
    url = candidates[index]
    loader = {"image": download_image_tensor, "video": download_video_object, "audio": download_audio_object}[kind]
    return (loader(client, url), url, task_id, json.dumps(urls, ensure_ascii=False),
            float(data.get("creditsConsumed") or 0.0))


def _reuse_class(kind: str):
    names = {"image": "IMAGE", "video": "VIDEO", "audio": "AUDIO"}

    class ReuseNode:
        CATEGORY = "KIE Next/Utility/Tasks"
        FUNCTION = "reuse"
        RETURN_TYPES = (names[kind], "STRING", "STRING", "STRING", "FLOAT")
        RETURN_NAMES = (kind, "url", "task_id", "all_urls_json", "historical_credits")
        DESCRIPTION = f"Retrieve and persist an existing completed KIE {kind} task. Queries status; never creates a new task or counts credits twice."

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"task_id": ("STRING", {"default": "", "multiline": False}),
                                 "result_index": ("INT", {"default": 0, "min": 0, "max": 20})},
                    "optional": {"config": ("KIE_CONFIG",)}}

        def reuse(self, task_id, result_index=0, config=None):
            return _existing_result(make_client(config), task_id, kind, int(result_index))

    ReuseNode.__name__ = f"KIEReuseCompleted{kind.title()}Node"
    return ReuseNode


KIEReuseCompletedImageNode = _reuse_class("image")
KIEReuseCompletedVideoNode = _reuse_class("video")
KIEReuseCompletedAudioNode = _reuse_class("audio")

REUSE_CLASS_MAPPINGS = {
    "KIE_Next_Reuse_Completed_Image": KIEReuseCompletedImageNode,
    "KIE_Next_Reuse_Completed_Video": KIEReuseCompletedVideoNode,
    "KIE_Next_Reuse_Completed_Audio": KIEReuseCompletedAudioNode,
}
REUSE_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Reuse_Completed_Image": "KIE • Reuse Completed Image",
    "KIE_Next_Reuse_Completed_Video": "KIE • Reuse Completed Video",
    "KIE_Next_Reuse_Completed_Audio": "KIE • Reuse Completed Audio",
}
