"""Typed outputs for models with documented result formats beyond the first URL."""
from __future__ import annotations

import json
import math
from typing import Any

from .client import KIEClient, pretty_json
from .media import download_image_asset, download_image_tensor, download_video_object, persist_result_bytes

_SEEDREAM_LAYERS = "seedream/5-5-layer-decomposition"
NEMOTRON_TRANSCRIBE = "nvidia/nemotron-3-5-transcribe"
_SEEDANCE_LAST_FRAME_MODELS = {
    "bytedance/seedance-2", "bytedance/seedance-2-fast", "bytedance/seedance-2-mini",
    "bytedance/seedance-2-5", "bytedance/seedance-2-5-flash", "bytedance/seedance-2-5-draft",
}
_GEMINI_OMNI_STILL_MODELS = {"google/gemini-omni-flash-1-1", "google/gemini-omni-flash-1-2", "gemini-omni-video"}
_OMNI_ASSET_FIELDS = {
    "/api/v1/omni/audio/create": ("audioId", "name"),
    "/api/v1/omni/character/create": ("characterId", "characterName", "imageUrl", "bodyImageUrl"),
}
_OMNI_ASSET_OUTPUTS = {
    "/api/v1/omni/audio/create": ("audio_id", "name"),
    "/api/v1/omni/character/create": ("character_id", "character_name", "image_url", "body_image_url"),
}


def model_output_slots(model: str, kind: str) -> tuple[tuple[str, str], ...]:
    if kind == "image":
        if model == _SEEDREAM_LAYERS:
            return (("MASK", "base_mask"), ("LAYERS", "layer_stack"), ("STRING", "layers_json"))
        if model == "kling-4-0/image":
            return (("STRING", "result_urls"),)
        if model.startswith("gpt-image-2-6/"):
            slots = (("MASK", "mask"), ("STRING", "image_file_path"))
            if model != "gpt-image-2-6/economy-image-to-image":
                slots += (("STRING", "frame_durations_ms_json"),)
            return slots
        if model in {"seedream/5-5-text-to-image", "seedream/5-5-image-to-image"}:
            return (("MASK", "mask"), ("STRING", "image_file_path"))
    if kind == "video" and model in _SEEDANCE_LAST_FRAME_MODELS:
        return (("IMAGE", "last_frame"), ("STRING", "last_frame_url"))
    if kind == "video" and model in _GEMINI_OMNI_STILL_MODELS:
        return (("IMAGE", "first_frame"), ("STRING", "first_frame_url"), ("IMAGE", "last_frame"), ("STRING", "last_frame_url"))
    if kind == "text" and model == NEMOTRON_TRANSCRIBE:
        return (
            ("STRING", "transcript_url"), ("FLOAT", "duration_seconds"),
            ("STRING", "text_with_speakers"), ("STRING", "words_json"),
            ("STRING", "diarization_json"), ("STRING", "transcript_file_path"),
        )
    return ()


def direct_asset_output_names(endpoint: str) -> tuple[str, ...]:
    return _OMNI_ASSET_OUTPUTS.get(endpoint, ())


def direct_asset_result(endpoint: str, payload: Any) -> tuple[str, ...]:
    data = _json_object(_json_object(payload).get("data"))
    return tuple(str(data.get(field) or "") for field in _OMNI_ASSET_FIELDS[endpoint])


def _json_object(value: Any) -> dict[str, Any]:
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _result_field(payload: Any, name: str) -> Any:
    """Inspect documented result fields without traversing request parameters."""
    record = _json_object(payload)
    record = _json_object(record.get("data")) or record
    for candidate in (record.get("response"), record.get("resultJson"), record):
        value = _json_object(candidate).get(name)
        if value:
            return value
    return None


def _result_urls(payload: Any, field: str) -> list[str]:
    value = _result_field(payload, field)
    candidates = value if isinstance(value, list) else [value]
    return [
        url for url in candidates
        if isinstance(url, str) and url.startswith(("http://", "https://"))
    ]


def primary_result_url(payload: Any, urls: list[str], *, kind: str) -> str:
    # KIE orders the base image before the layers and lists Seedance stills
    # separately, even when a CDN link has no identifiable file extension.
    result_urls = _result_urls(payload, "resultUrls")
    if result_urls:
        return result_urls[0]
    auxiliary = set(_result_urls(payload, "firstFrameUrl") + _result_urls(payload, "lastFrameUrl")) if kind == "video" else set()
    return next((url for url in urls if url not in auxiliary), "")


def _layer_stack(client: KIEClient, base_image, base_mask, layers: list, task_id: str):
    height, width = base_image.shape[1:3]
    items = [{
        "type": "raster", "image": base_image, "mask": base_mask,
        "x": 0, "y": 0, "z_index": 0, "name": "Background",
    }]
    seen = {0}
    for layer in layers:
        if not isinstance(layer, dict):
            return None
        z_index = layer.get("z_index")
        if z_index == 0:
            continue
        if type(z_index) is not int or z_index < 1 or z_index in seen:
            return None
        box = _json_object(layer.get("bounding_box")).get("absolute")
        url = layer.get("url")
        if (
            not isinstance(box, list) or len(box) != 4
            or any(type(value) is not int for value in box)
            or not isinstance(url, str) or not url.startswith(("https://", "http://"))
        ):
            return None
        left, top, right, bottom = box
        if right <= left or bottom <= top:
            return None
        try:
            layer_image, layer_mask, _, _ = download_image_asset(client, url)
        except Exception as exc:
            print(f"[KIE Next] Task {task_id}: could not prepare layer {z_index}. The layer URLs are in layers_json. {type(exc).__name__}")
            return None
        if layer_image is None:
            return None
        seen.add(z_index)
        items.append({
            "type": "raster", "image": layer_image, "mask": layer_mask, "x": left, "y": top,
            "w": right - left, "h": bottom - top, "z_index": z_index,
            "name": layer.get("name") or f"Layer {z_index}",
        })
    return {"version": 1, "canvas": (width, height), "layers": sorted(items, key=lambda item: item["z_index"])}


def model_image_result(
    client: KIEClient, model: str, payload: Any, url: str, task_id: str, output_format: str,
) -> tuple[Any, tuple]:
    if model == "kling-4-0/image":
        result_urls = _result_urls(payload, "resultUrls")
        return download_image_tensor(client, url), (result_urls or [url],)
    image, mask, durations, path = download_image_asset(client, url, output_format=output_format)
    if model == _SEEDREAM_LAYERS:
        layers = _json_object(_result_field(payload, "resultObject")).get("layers_data")
        layers = layers if isinstance(layers, list) else []
        stack = _layer_stack(client, image, mask, layers, task_id) if image is not None and layers else None
        return image, (mask, stack, pretty_json(layers))
    if model.startswith("gpt-image-2-6/") and model != "gpt-image-2-6/economy-image-to-image":
        return image, (mask, path, pretty_json(durations))
    return image, (mask, path)


def _video_frame(client: KIEClient, payload: Any, task_id: str, field: str) -> tuple[Any, str]:
    frame_urls = _result_urls(payload, field)
    frame_url = frame_urls[0] if frame_urls else ""
    frame = None
    if frame_url:
        try:
            frame = download_image_tensor(client, frame_url)
        except Exception as exc:
            print(f"[KIE Next] Task {task_id}: could not download {field}. The frame URL is available. {type(exc).__name__}")
    return frame, frame_url


def model_video_result(client: KIEClient, model: str, payload: Any, url: str, task_id: str) -> tuple[Any, tuple]:
    video = download_video_object(client, url)
    first = _video_frame(client, payload, task_id, "firstFrameUrl") if model in _GEMINI_OMNI_STILL_MODELS else ()
    return video, (*first, *_video_frame(client, payload, task_id, "lastFrameUrl"))


def nemotron_result(client: KIEClient, payload: Any, task_id: str) -> tuple[str, tuple]:
    summary = _json_object(_result_field(payload, "resultObject"))
    text = summary.get("text")
    text = text if isinstance(text, str) else ""
    duration = summary.get("duration")
    duration = float(duration) if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0 else -1.0
    url = summary.get("url")
    url = url if isinstance(url, str) and url.startswith(("https://", "http://")) else ""
    details: dict[str, Any] = {}
    file_path = ""
    if url:
        try:
            content = client.download_bytes(url)
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Expected an object in the transcript file")
            details = parsed
            file_path = persist_result_bytes(content, "", kind="files", fallback_suffix=".json") or ""
        except Exception as exc:
            print(f"[KIE Next] Task {task_id}: detailed transcript download failed. Transcript and URL are still available. {type(exc).__name__}")
    return text, (
        url, duration, str(details.get("text_with_speakers") or ""),
        pretty_json(details.get("words") or []), pretty_json(details.get("diarization") or []), file_path,
    )
