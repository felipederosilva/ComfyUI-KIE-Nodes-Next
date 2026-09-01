from __future__ import annotations

import json
from urllib.parse import quote
from typing import Any

from .client import KIEAPIError, KIEClient, KIEConfig, KIEResult, pretty_json


def make_client(config: KIEConfig | None = None) -> KIEClient:
    # v0.3 nodes normally call this with no input; credentials are resolved from
    # ComfyUI Settings. Passing KIE_CONFIG keeps v0.1 workflows compatible.
    if config is None:
        config = KIEConfig.from_values()
    if not isinstance(config, KIEConfig):
        raise KIEAPIError("KIE config input is invalid.")
    return KIEClient(config)


def parse_object_json(text: str, field_name: str = "JSON") -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise KIEAPIError(f"Invalid {field_name}: {exc}") from exc
    if not isinstance(value, dict):
        raise KIEAPIError(f"{field_name} must be a JSON object.")
    return value


def result_metadata(result: KIEResult) -> tuple[str, str, str, float]:
    return (
        result.task_id,
        json.dumps(result.urls, ensure_ascii=False),
        pretty_json(result.raw),
        float(result.credits_consumed),
    )


def require_first_url(result: KIEResult, kind: str = "media") -> str:
    if not result.urls:
        raise KIEAPIError(f"KIE task succeeded but no {kind} URL was found in resultJson.", payload=result.raw)
    return result.urls[0]


def replace_placeholders(value: Any, replacements: dict[str, Any]) -> Any:
    """Recursively replace exact placeholder tokens in raw API payloads."""
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    if isinstance(value, list):
        return [replace_placeholders(v, replacements) for v in value]
    if isinstance(value, dict):
        return {k: replace_placeholders(v, replacements) for k, v in value.items()}
    return value


def apply_path_params(endpoint: str, params: dict[str, object]) -> str:
    """Replace {name}/:name endpoint parameters using URL-encoded values."""
    value = endpoint
    for key, raw in params.items():
        encoded = quote(str(raw), safe="")
        value = value.replace("{" + str(key) + "}", encoded)
        value = value.replace(":" + str(key), encoded)
    return value

