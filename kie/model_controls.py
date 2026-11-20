"""Request controls for model conditions described in KIE's official specifications."""

from __future__ import annotations

from typing import Any


KIE_PROVIDER_DEFAULT = "Provider default"
SEEDANCE_FLASH = "bytedance/seedance-2-5-flash"
KLING_FLASH_KEYFRAME = "kling-4.0/flash-keyframe-to-video"
KLING_FLASH_REFERENCE = "kling-4.0/flash-reference-to-video"
KLING_IMAGE = "kling-4-0/image"
KLING_LONG_IMAGE = "kling-4-0/long-image"
GPT_IMAGE_26 = "gpt-image-2-6/"
GPT_IMAGE_26_ECONOMY_T2I = GPT_IMAGE_26 + "economy-text-to-image"
MINIMAX_H3_IMAGES = {"minimax-h3/text-to-image", "minimax-h3/image-edit"}
GEMINI_OMNI_12 = "google/gemini-omni-flash-1-2"
LTX_25_AUDIO = "ltx/2-5-fast-audio-to-video"
NEMOTRON_TRANSCRIBE = "nvidia/nemotron-3-5-transcribe"


def input_field_options(model: str, name: str, hint: dict[str, Any]) -> dict[str, Any]:
    """Adjust widget defaults and ranges without changing the provider schema."""
    options: dict[str, Any] = {}
    if model.startswith(GPT_IMAGE_26):
        if name in {"prompt", "mask_url", "markup"}:
            options["default"] = ""
        if name == "frame_duration_ms":
            options.update({"type": "integer", "minimum": 20, "maximum": 2000, "step": 10})
            if model == GPT_IMAGE_26_ECONOMY_T2I:
                options["minimum"] = 0
                options["default"] = 0
                options["description"] = "GIF only. Set 0 for automatic timing, or use 20–2000 ms per frame."
        if name == "output_compression":
            options.update({"minimum": -1, "default": -1})
            options["description"] = "JPEG or WebP only. Use -1 for the provider default, or set compression from 0 to 100."
    if model == SEEDANCE_FLASH and name == "duration":
        options.update({"enum": [-1, *range(4, 31)], "default": -1})
    if (model, name) in {
        (SEEDANCE_FLASH, "omni_reference_task_type"),
        (KLING_FLASH_REFERENCE, "aspect_ratio"),
        (NEMOTRON_TRANSCRIBE, "target_language"),
    } and hint.get("enum"):
        options.update({"enum": [KIE_PROVIDER_DEFAULT, *hint["enum"]], "default": KIE_PROVIDER_DEFAULT})
    if model == GEMINI_OMNI_12 and name == "character_ids":
        options["default"] = []
    if model == LTX_25_AUDIO and name == "duration":
        options.update({"default": 0.0, "minimum": 0.0})
        options["description"] = "Use 0 to follow the audio's length within the model limit.\n\n" + str(hint.get("description") or "")
    if model in MINIMAX_H3_IMAGES:
        if name in {"width", "height"}:
            options.update({"default": 0, "minimum": 0})
            options["description"] = "Set both dimensions to use custom sizing, or set both to 0 for the aspect ratio and resolution presets.\n\n" + str(hint.get("description") or "")
        if name == "seed":
            options.update({"default": -1, "minimum": -1})
            options["description"] = "Use -1 to let MiniMax choose the seed.\n\n" + str(hint.get("description") or "")
    if name == "prompt" and (model in {
        SEEDANCE_FLASH, KLING_IMAGE, KLING_LONG_IMAGE, KLING_FLASH_KEYFRAME, KLING_FLASH_REFERENCE,
        GEMINI_OMNI_12, GEMINI_OMNI_12 + "-extend", "omnihuman-2-0", *MINIMAX_H3_IMAGES,
    } or model.startswith(("seedream/5-5", "ltx/2-5-", "pixverse-v6-max/"))):
        options["default"] = ""
    return options


def normalize_model_input(model: str, payload: dict[str, Any]) -> None:
    """Remove inactive controls before validating or submitting an API request."""
    if model.startswith(GPT_IMAGE_26):
        output_format = payload.get("output_format") or "png"
        if output_format != "gif":
            for name in ("size", "frame_count", "frame_duration_ms"):
                payload.pop(name, None)
        elif model == GPT_IMAGE_26_ECONOMY_T2I:
            if payload.get("frame_duration_ms") == 0:
                payload.pop("frame_duration_ms", None)
        else:
            payload.pop("resolution", None)
            payload.pop("aspect_ratio", None)
        if output_format != "svg":
            payload.pop("svg", None)
        if output_format not in {"jpeg", "jpg", "webp"} or payload.get("output_compression") == -1:
            payload.pop("output_compression", None)
    elif model == KLING_LONG_IMAGE and payload.get("skill") == "webpage":
        payload.pop("length", None)
    elif model == KLING_FLASH_KEYFRAME and payload.get("first_frame_url"):
        payload.pop("aspect_ratio", None)
    elif model == KLING_FLASH_REFERENCE and not payload.get("video_urls"):
        payload.pop("keep_original_sound", None)
    elif model == GEMINI_OMNI_12:
        if payload.get("video_list"):
            payload.pop("duration", None)
        if payload.get("character_ids") == []:
            payload.pop("character_ids", None)
    elif model == LTX_25_AUDIO and payload.get("duration") == 0:
        payload.pop("duration", None)
    elif model in MINIMAX_H3_IMAGES:
        if payload.get("seed") == -1:
            payload.pop("seed", None)
        for name in ("width", "height"):
            if payload.get(name) == 0:
                payload.pop(name, None)
        if "width" in payload and "height" in payload:
            payload.pop("aspect_ratio", None)
            payload.pop("resolution", None)
