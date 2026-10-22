"""Read-only Market discovery and authoritative OpenAPI request definitions."""
from __future__ import annotations

import copy
import re
import time
from typing import Any
from urllib.parse import unquote

import requests


# These utility pages omit the outer Market ID. The IDs below are verified
# against their corresponding live KIE model schemas, not display-name guesses.
_UTILITY_DOC_MODELS = {
    "suno-api/generate-persona.md": "ai-music-api/generate-persona",
    "suno-api/recovery-audio.md": "ai-music-api/suno-recovery-audio",
    "veo3-api/get-veo-3-4k-video.md": "veo/get-4k-video",
}


def resolve_local_refs(value: Any, document: dict, trail: tuple = ()) -> Any:
    if isinstance(value, list):
        return [resolve_local_refs(item, document, trail) for item in value]
    if not isinstance(value, dict):
        return value
    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/") and ref not in trail:
        target: Any = document
        try:
            for part in ref[2:].split("/"):
                target = target[unquote(part).replace("~1", "/").replace("~0", "~")]
            return {**resolve_local_refs(target, document, (*trail, ref)),
                    **resolve_local_refs({k: v for k, v in value.items() if k != "$ref"}, document, trail)}
        except (KeyError, TypeError):
            pass
    return {key: resolve_local_refs(child, document, trail) for key, child in value.items()}


def request_definition(document: dict, endpoint: str, method: str) -> dict:
    operation = resolve_local_refs((document.get("paths", {}).get(endpoint) or {}).get(method.lower()) or {}, document)
    content = (operation.get("requestBody") or {}).get("content") or {}
    media = content.get("application/json") or next(iter(content.values()), {})
    schema = media.get("schema") or {}
    properties = schema.get("properties") or {}
    model_property = properties.get("model") or {}
    model_ids = list(model_property.get("enum") or [])
    if not model_ids and model_property.get("default"):
        model_ids = [model_property["default"]]
    if not model_ids and model_property.get("const"):
        model_ids = [model_property["const"]]
    if not model_ids and model_property.get("examples"):
        model_ids = [model_property["examples"][0]]
    example = media.get("example") or schema.get("example") or {}
    if not isinstance(example, dict):
        example = {}
    if not model_ids and isinstance(example.get("model"), str):
        model_ids = [example["model"]]
    market = endpoint == "/api/v1/jobs/createTask"
    controls = properties.get("input", {}) if market else schema
    if market:
        example = example.get("input") if isinstance(example.get("input"), dict) else {}
    # Keep each alternative intact for selection/validation; expose their union
    # as optional fields and require only controls shared by every branch.
    branches = controls.get("oneOf") or controls.get("anyOf") or []
    if branches:
        controls = copy.deepcopy(controls)
        properties = dict(controls.get("properties") or {})
        for branch in branches:
            for name, prop in (branch.get("properties") or {}).items():
                properties.setdefault(name, prop)
        controls["properties"] = properties
        controls["required"] = sorted(set(controls.get("required") or []) | set.intersection(*(set(branch.get("required") or []) for branch in branches)))
    return {"operation": operation, "schema": controls, "example": example,
            "model_ids": model_ids, "market_model": str(model_ids[0]) if market and model_ids else ""}


def merge_market_schemas(catalog: dict, models: list[dict], schemas: dict, *, verified_at: int | None = None) -> dict:
    """Enrich existing nodes in place, preserving their documentation identity."""
    from .catalog import _hint_from_schema, _operation_model_variants

    result = copy.deepcopy(catalog)
    now = int(verified_at or time.time())
    operations = result.setdefault("operations", [])
    inventory = {row["model"]: row for row in result.get("models", [])}
    unavailable: list[str] = []
    for model in models:
        model_id = model["model"]
        entry = schemas.get(model_id) or {}
        document = entry.get("openapi") or {}
        paths = [(path, verb.upper()) for path, verbs in document.get("paths", {}).items()
                 for verb in verbs if verb.lower() in {"get", "post", "put", "patch", "delete"}]
        row = {**inventory.get(model_id, {}), "model": model_id,
               "name": model.get("title") or model_id, "provider": model.get("provider") or "Other",
               "task_types": model.get("taskType") or [], "pricing_description": model.get("pricingDesc") or "",
               "market_schema_verified_at": now, "schema_available": bool(paths)}
        inventory[model_id] = row
        if not paths:
            unavailable.append(model_id)
            continue
        # Each model schema describes its own single callable operation.
        endpoint, method = next((item for item in paths if item[1] == "POST"), paths[0])
        definition = request_definition(document, endpoint, method)
        market_model = definition["market_model"]
        inner_models = ((definition["schema"].get("properties") or {}).get("model") or {}).get("enum") or []
        known_ids = {model_id, *definition["model_ids"], *inner_models}
        normalize_id = lambda value: re.sub(r"[^a-z0-9]", "", str(value).lower())
        normalized_ids = {normalize_id(value) for value in known_ids}
        op = next((candidate for candidate in operations
                   if ((market_model and candidate.get("market_model") == market_model)
                       or bool(known_ids.intersection(_operation_model_variants(candidate)))
                       or any(normalize_id(value) in normalized_ids for value in _operation_model_variants(candidate))
                       or any(str(candidate.get("docs_url") or "").endswith(path) and model_id == identifier for path, identifier in _UTILITY_DOC_MODELS.items())
                       or ("/" not in model_id and normalize_id(str(candidate.get("docs_url") or "").rsplit("/", 1)[-1].removesuffix(".md")) == normalize_id(model_id))
                       or (candidate.get("endpoint") == endpoint and not market_model and "/models/" in endpoint))), None)
        existing_operation = op is not None
        if op is None:
            tasks = model.get("taskType") or []
            root = "Chat Models" if "Chat" in tasks else "Video Models" if any("Video" in task for task in tasks) else "Music Models" if any("Music" in task or "Audio" in task or "Speech" in task for task in tasks) else "Image Models"
            family = root + " > " + str(model.get("provider") or "Other")
            title = model.get("title") or model_id
            op = {"title": title, "label": family + " • " + title, "family": family,
                  "docs_url": "https://api.kie.ai/api/v1/models/" + model_id + "/schema"}
            operations.append(op)
        old_variants = _operation_model_variants(op)
        control_schema = definition["schema"]
        properties = control_schema.get("properties") or {}
        required = set(control_schema.get("required") or [])
        hints = {name: _hint_from_schema(value, required=name in required)
                 for name, value in properties.items() if isinstance(value, dict)}
        # Versioned inputs (Suno) are distinct from the outer Market route ID.
        versions = (properties.get("model") or {}).get("enum") if market_model else definition["model_ids"]
        variants = list(versions or ([] if market_model and "model" in properties else [market_model or model_id]))
        if existing_operation and not old_variants and variants:
            op["legacy_unversioned"] = True
        aliases = dict(op.get("model_aliases") or {})
        for old in old_variants:
            for current in variants:
                if old != current and normalize_id(old) == normalize_id(current):
                    aliases[old] = current
        if aliases:
            op["model_aliases"] = aliases
        op.update({"method": method, "endpoint": endpoint, "resolved": True,
                   "models": list(dict.fromkeys([*old_variants, *variants])),
                   "parameter_hints": hints, "example_body": definition["example"],
                   "input_schema": control_schema, "market_catalog_id": model_id,
                   "schema_source": "KIE model OpenAPI", "schema_verified_at": now})
        if market_model:
            op["market_model"] = market_model
        description = definition["operation"].get("description") or model.get("description")
        if description:
            op["summary"] = str(description)[:700]
        row.update({"family": op["family"], "docs_url": op["docs_url"], "method": method,
                    "endpoint": endpoint, "transport": "market_task" if market_model else "direct"})
    result["models"] = sorted(inventory.values(), key=lambda row: (str(row.get("family")), row["model"]))
    result["operations"] = sorted(operations, key=lambda op: str(op.get("label", "")))
    result.update({"market_models_total": len(models), "market_schemas_available": len(models) - len(unavailable),
                   "market_schemas_unavailable": unavailable, "market_checked_at": now})
    return result


def sync_market_schemas(catalog: dict, api_key: str) -> dict:
    """GET-only discovery, rate limited to KIE's shared one-request/second quota."""
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + api_key
    last_request = 0.0

    def get(path):
        nonlocal last_request
        delay = 1.15 - (time.monotonic() - last_request)
        if delay > 0:
            time.sleep(delay)
        last_request = time.monotonic()
        response = session.get("https://api.kie.ai/api/v1/models" + path, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise ValueError("KIE model discovery failed: " + str(payload.get("code")))
        return payload.get("data") or {}

    models = get("").get("models") or []
    if not models:
        return catalog
    now = int(time.time())
    cached = {row["model"]: row for row in catalog.get("models", [])}
    pending = [row for row in models if not cached.get(row["model"], {}).get("schema_available") or now - int(cached.get(row["model"], {}).get("market_schema_verified_at") or 0) >= 86400 * 7]
    schemas = {row["model"]: get("/" + row["model"] + "/schema") for row in pending}
    result = merge_market_schemas(catalog, pending, schemas) if pending else copy.deepcopy(catalog)
    result["market_models_total"] = len(models)
    result["market_checked_at"] = now
    rows = {row["model"]: row for row in result.get("models", [])}
    for row in models:
        if row["model"] in rows:
            rows[row["model"]].update({"provider": row.get("provider") or "Other",
                                       "task_types": row.get("taskType") or [],
                                       "pricing_description": row.get("pricingDesc") or ""})
    unavailable = [row["model"] for row in models if not rows.get(row["model"], {}).get("schema_available")]
    result["market_schemas_unavailable"] = unavailable
    result["market_schemas_available"] = len(models) - len(unavailable)
    return result
