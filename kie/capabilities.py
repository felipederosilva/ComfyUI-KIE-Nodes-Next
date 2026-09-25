"""Offline capability inspection and validation of documented request constraints.

This module never creates a client, uploads media, or submits a generation.
Missing documentation stays unknown; it is not interpreted as lack of support.
"""
from __future__ import annotations

import math
from typing import Any


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


def check_operation(op: dict[str, Any], payload: dict[str, Any], *, model: str = "",
                    media_fields=(), deferred_fields=()) -> dict[str, Any]:
    """Check only explicit constraints. Media content/remote availability remain unchecked."""
    errors: list[str] = []
    warnings: list[str] = []
    media_fields, deferred_fields = set(media_fields), set(deferred_fields)
    hints = op.get("parameter_hints") or {}

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
        "wan/3-0-video", "wan/3-0-video-prime",
    }
    if model in frame_models:
        frames = any(_present(payload.get(key)) for key in ("first_frame_url", "last_frame_url"))
        refs = any(_present(value) for key, value in payload.items() if key.startswith("reference_") and key.endswith("_urls"))
        if frames and refs:
            errors.append("First/last frames and reference inputs cannot be combined. Choose frame mode or reference mode.")
        if _present(payload.get("last_frame_url")) and not _present(payload.get("first_frame_url")):
            errors.append("last_frame_url: connect a first frame as well.")
    if model in {"wan/3-0-video", "wan/3-0-video-prime"} and _present(payload.get("reference_file_urls")) and _present(payload.get("reference_link_urls")):
        errors.append("File and link references cannot be combined in this Wan operation.")
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
