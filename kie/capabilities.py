"""Offline capability inspection and validation of documented request constraints.

This module never creates a client, uploads media, or submits a generation.
Missing documentation stays unknown; it is not interpreted as lack of support.
"""
from __future__ import annotations

import math
import re
from typing import Any

from .model_controls import (
    GEMINI_OMNI_12, GPT_IMAGE_26, GPT_IMAGE_26_ECONOMY_T2I, KLING_FLASH_KEYFRAME, KLING_FLASH_REFERENCE,
    KLING_IMAGE, KLING_LONG_IMAGE, MINIMAX_H3_IMAGES, NEMOTRON_TRANSCRIBE, SEEDANCE_FLASH,
)


def operation_capabilities(op: dict[str, Any], model: str = "") -> dict[str, Any]:
    hints = op.get("parameter_hints") or {}

    body = op.get("example_body") or {}
    if isinstance(body.get("input"), dict):
        body = body["input"]
    fields = {}
    for name in dict.fromkeys([*hints, *body, *(op.get("example_query") or {}), *(op.get("path_params") or [])]):
        hint = hints.get(name) or {}
        fields[name] = {
            "evidence": "parameter_metadata" if hint else "example",
            **{key: hint[key] for key in (
                "type", "required", "description", "enum", "default", "minimum", "maximum",
                "minLength", "maxLength", "minItems", "maxItems", "items", "properties", "nullable",
            ) if key in hint},
        }
    camera_fields = [name for name in fields if name.lower() in {
        "camera_control", "camera_controls", "camera_motion", "camera_movement", "camera_fixed", "camera",
    }]
    return {
        "model": model, "title": op.get("title", "KIE model"),
        "source": op.get("docs_url", ""),
        "coverage": "documented_fields" if hints else "examples_only" if fields else "unknown",
        "fields": fields,
        "camera": {
            "mode": "api_fields" if camera_fields else "prompt_guidance" if "prompt" in fields else "unknown",
            "fields": camera_fields,
            "note": "Camera Director describes the shot in the prompt. A native camera adapter is only available when explicitly implemented for the model.",
        },
    }


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, (str, list, dict)) and len(value) == 0)


def _kling_material_errors(model, payload, deferred):
    """Validate the item budgets and @ references documented for Kling 4.0."""
    errors = []
    images = payload.get("image_urls")
    videos = payload.get("video_urls")
    elements = payload.get("elements")
    images = images if isinstance(images, list) else []
    videos = videos if isinstance(videos, list) else []
    elements = elements if isinstance(elements, list) else []
    names = set()
    video_elements = 0
    reserved = r"(?:image|object)_\d+" if model == KLING_IMAGE else r"(?:(?:image|video|keyframe|object|audio)_\d+|first_frame|last_frame)"
    for index, element in enumerate(elements, 1):
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or "")
        tag = element.get("tag")
        if not re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9_]{1,20}", name) or re.fullmatch(reserved, name, flags=re.I):
            errors.append(f"Element {index}: choose a non-reserved name with 1–20 letters, digits, underscores, or Chinese characters.")
        elif name.casefold() in names:
            errors.append(f"Element {index}: the name '{name}' is already used.")
        else:
            names.add(name.casefold())
        if model != KLING_FLASH_REFERENCE:
            continue
        if element.get("type") == "video":
            video_elements += 1
            if not _present(element.get("video_url")) or _present(element.get("image_urls")):
                errors.append(f"Element {index}: a video subject needs one video_url and no image_urls.")
            if tag not in (None, "character"):
                errors.append(f"Element {index}: video subjects must use the character tag.")
        else:
            refs = element.get("image_urls")
            if not isinstance(refs, list) or not 2 <= len(refs) <= 4 or _present(element.get("video_url")):
                errors.append(f"Element {index}: an image subject needs 2–4 image URLs and no video_url.")
            if _present(element.get("voice_url")) and tag not in (None, "character"):
                errors.append(f"Element {index}: voice_url can only be bound to a character subject.")
    if model == KLING_IMAGE and len(images) + len(elements) > 10:
        errors.append("Kling Image 4.0 allows up to 10 reference images and elements combined.")
    if model == KLING_FLASH_REFERENCE:
        if video_elements > 3 or len(videos) + video_elements > 5:
            errors.append("Kling 4.0 Flash allows up to 3 video elements and 5 references and elements containing video combined.")
        if len(images) + len(videos) + len(elements) > 15:
            errors.append("Kling 4.0 Flash allows up to 15 reference images, videos, and elements combined.")
        if _present(payload.get("voices")):
            errors.append("Kling 4.0 Flash: set voice_url on a character element.")
    if "prompt" in deferred:
        return errors
    available = names | {f"image_{i}" for i in range(1, len(images) + 1)}
    available.update(f"video_{i}" for i in range(1, len(videos) + 1))
    if model == KLING_FLASH_KEYFRAME and _present(payload.get("first_frame_url")):
        available.add("first_frame")
    if model == KLING_LONG_IMAGE:
        if _present(payload.get("style_image")):
            available.add("style")
        if _present(payload.get("subject_image")):
            available.add("subject")
    for mention in dict.fromkeys(re.findall(r"@([\u4e00-\u9fa5A-Za-z0-9_]+)", str(payload.get("prompt") or ""))):
        key = mention.casefold()
        if key in available:
            continue
        if model == KLING_IMAGE and any(
            key.startswith(name) and re.search(r"[\u4e00-\u9fa5]$", name) for name in names
        ):
            continue  # Kling Image allows Chinese prose immediately after a Chinese element name.
        field = {"first_frame": "first_frame_url", "style": "style_image", "subject": "subject_image"}.get(key, "elements")
        if re.fullmatch(r"image_\d+", key):
            field = "image_urls"
        if re.fullmatch(r"video_\d+", key):
            field = "video_urls"
        if field not in deferred:
            errors.append(f"@{mention}: connect or declare the referenced Kling material.")
    return errors


def _gpt_image_errors(model, payload, deferred):
    errors = []
    output_format = payload.get("output_format") or "png"
    if "output_format" in deferred:
        return errors
    if payload.get("background") == "transparent" and output_format not in {"png", "webp", "gif"}:
        errors.append("Transparent GPT Image 2.6 output requires PNG, WebP, or GIF.")
    if _present(payload.get("mask_url")) and output_format in {"gif", "svg"}:
        errors.append("mask_url: select a static raster output to use an inpaint mask.")
    if _present(payload.get("mask_url")) and _present(payload.get("markup")):
        errors.append("Choose either mask_url or markup for a GPT Image 2.6 edit.")
    if output_format != "gif":
        return errors
    duration = payload.get("frame_duration_ms")
    if model == GPT_IMAGE_26_ECONOMY_T2I:
        if duration is not None and (not isinstance(duration, int) or isinstance(duration, bool) or not 20 <= duration <= 2000):
            errors.append("frame_duration_ms: choose automatic timing or an integer from 20 to 2000.")
        return errors
    if isinstance(duration, int) and duration % 10 != 0:
        errors.append("frame_duration_ms: choose a multiple of 10 ms.")
    size = payload.get("size")
    if not _present(size) or size == "auto":
        return errors
    match = re.fullmatch(r"(\d{1,5})x(\d{1,5})", str(size), flags=re.I)
    if not match:
        return [*errors, "size: choose auto or enter GIF frame dimensions such as 512x512."]
    width, height = map(int, match.groups())
    if min(width, height) < 16 or width % 16 or height % 16:
        return [*errors, "size: both GIF frame dimensions must be positive multiples of 16."]
    count = payload.get("frame_count", 9)
    if "frame_count" in deferred or not isinstance(count, int) or not 2 <= count <= 16:
        return errors
    columns, rows = (4, 2) if count <= 8 else (3, 3) if count == 9 else (4, 3) if count <= 12 else (4, 4)
    dimensions = [(width * columns, height * rows), (width * rows, height * columns)]
    if not any(max(w, h) <= 3840 and w * h <= 8294400 and max(w, h) <= 3 * min(w, h) for w, h in dimensions):
        errors.append("size and frame_count exceed the provider's GIF sprite sheet limits. Try 512x512 frames.")
    return errors


def check_operation(op: dict[str, Any], payload: dict[str, Any], *, model: str = "",
                    media_fields=(), deferred_fields=()) -> dict[str, Any]:
    """Check only explicit constraints. Media content/remote availability remain unchecked."""
    errors: list[str] = []
    warnings: list[str] = []
    media_fields, deferred_fields = set(media_fields), set(deferred_fields)
    hints = op.get("parameter_hints") or {}
    input_schema = op.get("input_schema") or {}
    alternatives = input_schema.get("anyOf") or input_schema.get("oneOf") or []
    if alternatives and not any(branch.get("properties") for branch in alternatives):
        if not any(all(_present(payload.get(key)) or key in deferred_fields for key in branch.get("required", [])) for branch in alternatives):
            errors.append("Provide one of the documented input alternatives: " + " or ".join(
                ", ".join(branch.get("required") or []) for branch in alternatives))

    def validate(name, value, schema, depth=0):
        if depth > 12 or not isinstance(schema, dict):
            return
        if any(key in schema for key in ("$ref", "oneOf", "anyOf", "allOf")):
            warnings.append(f"{name}: conditional schema requires provider validation.")
            return
        if value is None and schema.get("nullable"):
            return
        typ = schema.get("type")
        expected = {
            "string": isinstance(value, str), "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "array": isinstance(value, list), "object": isinstance(value, dict),
        }
        if isinstance(typ, str) and typ in expected and not expected[typ]:
            errors.append(f"{name}: expected {typ}.")
            return
        if schema.get("enum") and value not in schema["enum"]:
            errors.append(f"{name}: choose one of {', '.join(map(str, schema['enum']))}.")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                errors.append(f"{name}: must be a finite number.")
                return
            for key, bad, word in (("minimum", lambda limit: value < limit, "at least"), ("maximum", lambda limit: value > limit, "at most")):
                limit = schema.get(key)
                if isinstance(limit, (int, float)) and bad(limit):
                    errors.append(f"{name}: must be {word} {limit}.")
        if isinstance(value, (str, list)):
            keys = ("minLength", "maxLength") if isinstance(value, str) else ("minItems", "maxItems")
            unit = "characters" if isinstance(value, str) else "items"
            for key, bad, word in ((keys[0], lambda limit: len(value) < limit, "at least"), (keys[1], lambda limit: len(value) > limit, "at most")):
                limit = schema.get(key)
                if isinstance(limit, int) and bad(limit):
                    errors.append(f"{name}: needs {word} {limit} {unit}.")
        if isinstance(value, list) and isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                validate(f"{name}[{index}]", item, schema["items"], depth + 1)
        if isinstance(value, dict):
            required = schema.get("required_properties", schema.get("required"))
            for key in required if isinstance(required, list) else []:
                if not _present(value.get(key)):
                    errors.append(f"{name}.{key}: required.")
            for key, child in (schema.get("properties") or {}).items():
                if key in value:
                    validate(f"{name}.{key}", value[key], child, depth + 1)

    for name, hint in hints.items():
        if name in deferred_fields:
            continue
        value = payload.get(name)
        if hint.get("required") and (not _present(value) or isinstance(value, str) and not value.strip()):
            errors.append(f"{name}: required.")
            continue
        if name not in payload:
            continue
        if name in media_fields:
            # Some provider schemas incorrectly describe URL media as empty objects.
            # Native media type/count is checked here; byte format and URL availability
            # cannot be established by the offline schema validator.
            if isinstance(value, list):
                validate(name, value, {key: hint[key] for key in ("minItems", "maxItems") if key in hint})
            continue
        validate(name, value, hint)

    # Official Seedance/Wan docs prohibit combining frame mode with references.
    frame_models = {
        "bytedance/seedance-2", "bytedance/seedance-2-fast", "bytedance/seedance-2-mini", "bytedance/seedance-2-5",
        "wan/3-0-video", "wan/3-0-video-prime", SEEDANCE_FLASH,
    }
    if model in frame_models:
        frames = any(_present(payload.get(key)) for key in ("first_frame_url", "last_frame_url"))
        refs = any(_present(value) for key, value in payload.items() if key.startswith("reference_") and key.endswith("_urls"))
        if frames and refs:
            errors.append("First/last frames and reference inputs cannot be combined. Choose frame mode or reference mode.")
        if _present(payload.get("last_frame_url")) and not _present(payload.get("first_frame_url")) and "first_frame_url" not in deferred_fields:
            errors.append("last_frame_url: connect a first frame as well.")
    if model == SEEDANCE_FLASH:
        duration = payload.get("duration")
        aspect = payload.get("aspect_ratio")
        task_type = payload.get("omni_reference_task_type")
        if isinstance(duration, int) and duration != -1 and not 4 <= duration <= 30:
            errors.append("Seedance 2.5 Flash duration must be -1 (automatic) or 4–30 seconds.")
        if frames and aspect not in (None, "adaptive"):
            errors.append("Seedance 2.5 Flash frame inputs require adaptive aspect ratio.")
        known_refs = refs or bool({"reference_image_urls", "reference_video_urls", "reference_audio_urls"} & deferred_fields)
        if task_type and not known_refs:
            errors.append("omni_reference_task_type: connect a reference or select Provider default for text/first-frame generation.")
        if not frames and not known_refs and "prompt" not in deferred_fields and not str(payload.get("prompt") or "").strip():
            errors.append("prompt: enter a video description when no frame or reference is connected.")
        if task_type in {"edit", "extend"}:
            if not _present(payload.get("reference_video_urls")) and "reference_video_urls" not in deferred_fields:
                errors.append(f"Seedance 2.5 Flash {task_type} requires a reference video.")
            if "aspect_ratio" not in deferred_fields and aspect != "adaptive":
                errors.append(f"Seedance 2.5 Flash {task_type} requires adaptive aspect ratio.")
        if task_type == "edit" and "duration" not in deferred_fields and duration != -1:
            errors.append("Seedance 2.5 Flash edit requires automatic duration (-1).")
    if model in {KLING_IMAGE, KLING_LONG_IMAGE, KLING_FLASH_KEYFRAME, KLING_FLASH_REFERENCE}:
        errors.extend(_kling_material_errors(model, payload, deferred_fields))
    if model == KLING_IMAGE and not {"mode", "count"} & deferred_fields:
        count = payload.get("count")
        if payload.get("mode") == "series" and (not isinstance(count, int) or not 2 <= count <= 10):
            errors.append("Kling Image 4.0 Series needs a count of 2–10.")
        elif payload.get("mode") != "series" and isinstance(count, int) and count > 9:
            errors.append("Kling Image 4.0 Default supports at most 9 images.")
    if model == KLING_LONG_IMAGE and "skill" not in deferred_fields:
        if payload.get("skill") == "ecommerce":
            if not _present(payload.get("image_urls")) and "image_urls" not in deferred_fields:
                errors.append("Kling Long Image ecommerce requires 1–3 product images.")
            if any(_present(payload.get(field)) for field in ("style_image", "subject_image")):
                errors.append("Kling Long Image style_image and subject_image are for webpage mode.")
        elif payload.get("skill") == "webpage" and _present(payload.get("image_urls")):
            errors.append("Kling Long Image webpage mode uses style_image and subject_image. Disconnect product images.")
    if model.startswith(GPT_IMAGE_26):
        errors.extend(_gpt_image_errors(model, payload, deferred_fields))
    if model in {"seedream/5-5-text-to-image", "seedream/5-5-image-to-image"} and (
        "output_format" not in deferred_fields and payload.get("background") == "transparent" and payload.get("output_format", "png") != "png"
    ):
        errors.append("Seedream 5.5 transparency requires PNG output.")
    if model in MINIMAX_H3_IMAGES and not {"width", "height"} & deferred_fields:
        width, height = payload.get("width"), payload.get("height")
        if (width is None) != (height is None):
            errors.append("MiniMax H3 custom size requires both width and height.")
        elif isinstance(width, int) and isinstance(height, int) and (
            not 655360 <= width * height <= 20000000 or min(width, height) <= 0 or max(width, height) > 3 * min(width, height)
        ):
            errors.append("MiniMax H3 custom size needs 655,360–20,000,000 total pixels and a ratio from 1:3 to 3:1.")
    if model == GEMINI_OMNI_12:
        first_frame = _present(payload.get("first_frame_url"))
        last_frame = _present(payload.get("last_frame_url"))
        is_edit = _present(payload.get("video_list"))
        if last_frame and not first_frame and "first_frame_url" not in deferred_fields:
            errors.append("Gemini Omni 1.2 last_frame_url requires a first frame.")
        if (first_frame or last_frame) and any(_present(payload.get(key)) for key in ("image_urls", "character_ids", "video_list")):
            errors.append("Gemini Omni 1.2 frame inputs cannot be combined with references, character IDs, or a video to edit.")
        if not is_edit and not {"duration", "video_list"} & deferred_fields:
            duration = payload.get("duration")
            limit = 10 if last_frame else 15
            if not isinstance(duration, int) or not 3 <= duration <= limit:
                errors.append(f"Gemini Omni 1.2 requires a duration from 3 to {limit} seconds in this mode.")
    if model.startswith("ltx/2-5-fast-"):
        duration = payload.get("duration")
        if (payload.get("resolution") == "1440p" or payload.get("fps") in (48, 50)) and isinstance(duration, (int, float)) and duration > 10:
            errors.append("LTX 2.5 Fast: choose at most 10 seconds at 1440p or 48/50 fps.")
    if model == "omnihuman-2-0" and "image_urls" not in deferred_fields:
        images = payload.get("image_urls")
        if isinstance(images, list) and len(images) != 1:
            errors.append("OmniHuman 2.0 expects a single source image. Select one image from the batch.")
    if model == NEMOTRON_TRANSCRIBE and payload.get("timestamps") and payload.get("target_language"):
        errors.append("Nemotron 3.5 word timings and speakers are available in transcription mode. Choose Provider default for target_language.")
    if model in {"wan/3-0-video", "wan/3-0-video-prime"} and _present(payload.get("reference_file_urls")) and _present(payload.get("reference_link_urls")):
        errors.append("File and link references cannot be combined in this Wan operation.")
    if model == "kling-4.0/keyframe-to-video":
        keyframes = payload.get("keyframe_urls") or []
        available = {f"keyframe_{index + 1}" for index in range(len(keyframes))}
        for name in ("first_frame", "last_frame"):
            if _present(payload.get(name + "_url")):
                available.add(name)
        duration = payload.get("duration", 5)
        if isinstance(duration, int) and len(available) > min(duration + 1, 10):
            errors.append("Kling 4.0: total first/middle/last frames cannot exceed min(duration + 1, 10).")
        for mention in re.findall(r"@([A-Za-z_][A-Za-z_0-9]*)", str(payload.get("prompt") or "")):
            field = "keyframe_urls" if mention.startswith("keyframe_") else mention + "_url"
            if mention not in available and field not in deferred_fields:
                errors.append(f"@{mention}: connect the corresponding Kling keyframe before generation.")
    if not hints:
        warnings.append("This catalog entry has no parameter schema; documented limits could not be checked.")
    else:
        warnings.append("Rules written only in descriptions, and provider-side conditions, may require additional validation.")
    if media_fields:
        warnings.append("Media file format, dimensions, duration and remote availability are not validated by this check.")
    if deferred_fields:
        warnings.append("Connected values need execution before their final values and batch sizes can be checked: " + ", ".join(sorted(deferred_fields)))
    return {
        "valid": not errors, "errors": errors, "warnings": warnings,
        "capabilities": operation_capabilities(op, model),
        "scope": "Documented local constraints only; this check does not guarantee provider acceptance.",
    }


def require_valid(report: dict[str, Any]) -> None:
    if report["errors"]:
        raise ValueError("KIE input check failed before upload or generation:\n" + "\n".join(report["errors"]))
