from __future__ import annotations

import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import requests

try:
    import yaml
except ImportError:  # Optional at runtime; complete schemas are bundled in releases.
    yaml = None

from .settings import settings_path

LLMS_URL = "https://docs.kie.ai/llms.txt"
DOC_TIMEOUT = 25
_SYNC_LOCK = threading.Lock()
_CATALOG_WRITE_LOCK = threading.RLock()

# Immediate/offline fallback. Live sync expands this automatically.
SEED_MODELS = [
    {"name": "Seedance 1.5 Pro", "model": "bytedance/seedance-1.5-pro", "family": "Video / ByteDance / Seedance", "transport": "market_task"},
    {"name": "Seedance 2.0", "model": "bytedance/seedance-2", "family": "Video / ByteDance / Seedance", "transport": "market_task"},
    {"name": "Seedance 2.0 Fast", "model": "bytedance/seedance-2-fast", "family": "Video / ByteDance / Seedance", "transport": "market_task"},
    {"name": "Seedance 2.0 Mini", "model": "bytedance/seedance-2-mini", "family": "Video / ByteDance / Seedance", "transport": "market_task"},
    {"name": "Seedance 2.5", "model": "bytedance/seedance-2-5", "family": "Video / ByteDance / Seedance", "transport": "market_task"},
    {"name": "Kling 3.0", "model": "kling-3.0/video", "family": "Video / Kling", "transport": "market_task"},
    {"name": "Kling 3.0 Omni · Text", "model": "kling-3.0-omni/text-to-video", "family": "Video / Kling", "transport": "market_task"},
    {"name": "Kling 3.0 Omni · Image", "model": "kling-3.0-omni/image-to-video", "family": "Video / Kling", "transport": "market_task"},
    {"name": "Kling 3.0 Omni · Reference", "model": "kling-3.0-omni/reference-to-video", "family": "Video / Kling", "transport": "market_task"},
    {"name": "GPT Image 2 · Text", "model": "gpt-image-2-text-to-image", "family": "Image / OpenAI / GPT Image", "transport": "market_task"},
    {"name": "GPT Image 2 · Edit", "model": "gpt-image-2-image-to-image", "family": "Image / OpenAI / GPT Image", "transport": "market_task"},
    {"name": "Nano Banana 2", "model": "nano-banana-2", "family": "Image / Google / Nano Banana", "transport": "market_task"},
    {"name": "Seedream 5 Pro · Text", "model": "seedream/5-pro-text-to-image", "family": "Image / ByteDance / Seedream", "transport": "market_task"},
    {"name": "Seedream 5 Pro · Edit", "model": "seedream/5-pro-image-to-image", "family": "Image / ByteDance / Seedream", "transport": "market_task"},
    {"name": "Seedream 5 Lite · Text", "model": "seedream/5-lite-text-to-image", "family": "Image / ByteDance / Seedream", "transport": "market_task"},
    {"name": "Seedream 5 Lite · Edit", "model": "seedream/5-lite-image-to-image", "family": "Image / ByteDance / Seedream", "transport": "market_task"},
    {"name": "Wan 3.0 Video", "model": "wan/3-0-video", "family": "Video / Wan", "transport": "market_task"},
    {"name": "Wan 3.0 Video Prime", "model": "wan/3-0-video-prime", "family": "Video / Wan", "transport": "market_task"},
    {"name": "Claude Opus 5", "model": "claude-opus-5", "family": "LLM / Claude / Opus", "transport": "direct"},
    {"name": "GPT 5.6 Sol", "model": "gpt-5-6-sol", "family": "LLM / OpenAI / GPT", "transport": "direct"},
    {"name": "Suno V4", "model": "V4", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Suno V4.5", "model": "V4_5", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Suno V4.5 Plus", "model": "V4_5PLUS", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Suno V4.5 All", "model": "V4_5ALL", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Suno V5", "model": "V5", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Suno V5.5", "model": "V5_5", "family": "Audio / Suno / Music Generation", "transport": "direct"},
    {"name": "Veo 3 Fast", "model": "veo3_fast", "family": "Video / Google / Veo", "transport": "direct"},
]

# A compact offline bootstrap so the most important model families are already
# polished on the very first launch. KIE Next then replaces/expands this from the
# official live catalog automatically -- these are not the full catalog.
SEED_OPERATIONS: list[dict[str, Any]] = [
    {
        "label": "Video Models > Bytedance • Bytedance Seedance 1.5 Pro",
        "title": "Seedance 1.5 Pro",
        "family": "Video Models > Bytedance",
        "method": "POST", "endpoint": "/api/v1/jobs/createTask", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/bytedance/seedance-1-5-pro.md",
        "models": ["bytedance/seedance-1.5-pro"],
        "summary": "ByteDance Seedance 1.5 Pro video generation with prompt, image references, duration, resolution, lens/audio and safety controls.",
        "example_body": {"model": "bytedance/seedance-1.5-pro", "input": {
            "prompt": "", "input_urls": [], "aspect_ratio": "16:9", "resolution": "720p",
            "duration": 5, "fixed_lens": False, "generate_audio": True, "nsfw_checker": True,
        }},
    },
    {
        "label": "Video Models > Bytedance • bytedance-seedance-2",
        "title": "Seedance 2.0",
        "family": "Video Models > Bytedance",
        "method": "POST", "endpoint": "/api/v1/jobs/createTask", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/bytedance/seedance-2.md",
        "models": ["bytedance/seedance-2"],
        "summary": "Seedance 2.0 with text, first/last-frame, multimodal image/video/audio references, audio generation and web search.",
        "example_body": {"model": "bytedance/seedance-2", "input": {
            "prompt": "", "first_frame_url": "", "last_frame_url": "", "reference_image_urls": [],
            "reference_video_urls": [], "reference_audio_urls": [], "return_last_frame": False,
            "generate_audio": True, "resolution": "720p", "aspect_ratio": "16:9", "duration": 5, "web_search": False,
        }},
    },
    {
        "label": "Video Models > Bytedance • Bytedance Seedance 2.0 Fast",
        "title": "Seedance 2.0 Fast",
        "family": "Video Models > Bytedance",
        "method": "POST", "endpoint": "/api/v1/jobs/createTask", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/bytedance/seedance-2-fast.md",
        "models": ["bytedance/seedance-2-fast"],
        "summary": "Fast Seedance 2.0 generation with first/last frames and multimodal reference inputs.",
        "example_body": {"model": "bytedance/seedance-2-fast", "input": {
            "prompt": "", "first_frame_url": "", "last_frame_url": "", "reference_image_urls": [],
            "reference_video_urls": [], "reference_audio_urls": [], "return_last_frame": False,
            "generate_audio": True, "resolution": "720p", "aspect_ratio": "16:9", "duration": 5, "web_search": False,
        }},
    },
    {
        "label": "Video Models > Bytedance • Bytedance Seedance 2.0 Mini",
        "title": "Seedance 2.0 Mini",
        "family": "Video Models > Bytedance",
        "method": "POST", "endpoint": "/api/v1/jobs/createTask", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/bytedance/seedance-2-mini.md",
        "models": ["bytedance/seedance-2-mini"],
        "summary": "Seedance 2.0 Mini generation with first/last frames and multimodal reference inputs.",
        "example_body": {"model": "bytedance/seedance-2-mini", "input": {
            "prompt": "", "first_frame_url": "", "last_frame_url": "", "reference_image_urls": [],
            "reference_video_urls": [], "reference_audio_urls": [], "return_last_frame": False,
            "generate_audio": True, "resolution": "720p", "aspect_ratio": "16:9", "duration": 5, "web_search": False,
        }},
    },
    {
        "label": "Video Models > Bytedance • Bytedance Seedance 2.5",
        "title": "Seedance 2.5",
        "family": "Video Models > Bytedance",
        "method": "POST", "endpoint": "/api/v1/jobs/createTask", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/bytedance/seedance-2-5.md",
        "models": ["bytedance/seedance-2-5"],
        "summary": "Seedance 2.5 with image/video/audio references, generated audio, resolution, aspect ratio and duration controls.",
        "example_body": {"model": "bytedance/seedance-2-5", "input": {
            "prompt": "", "reference_image_urls": [], "reference_video_urls": [], "reference_audio_urls": [],
            "return_last_frame": False, "generate_audio": True, "resolution": "720p", "aspect_ratio": "16:9", "duration": 5,
        }},
    },
    {
        "label": "Chat Models > Claude • Claude Opus 5",
        "title": "Claude Opus 5", "family": "Chat Models > Claude",
        "method": "POST", "endpoint": "/claude/v1/messages", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/claude/claude-opus-5.md", "models": ["claude-opus-5"],
        "summary": "Claude Opus 5 chat with system prompt, conversation history, tools, thinking and streaming support.",
        "example_body": {"model": "claude-opus-5", "messages": [{"role": "user", "content": "Hello"}], "tools": [], "thinkingFlag": True, "stream": False, "max_tokens": 4096},
    },
    {
        "label": "Chat Models > GPT • GPT 5.6 Sol",
        "title": "GPT 5.6 Sol", "family": "Chat Models > GPT",
        "method": "POST", "endpoint": "/codex/v1/responses", "resolved": True,
        "docs_url": "https://docs.kie.ai/market/chat/gpt-5-6-sol.md", "models": ["gpt-5-6-sol"],
        "summary": "GPT 5.6 Sol multimodal responses API with reasoning effort, image input, web search or function tools.",
        "example_body": {"model": "gpt-5-6-sol", "input": [{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}], "reasoning": {"effort": "high"}},
    },
    {
        "label": "Suno API > Music Generation • Generate Music",
        "title": "Generate Music", "family": "Suno API > Music Generation",
        "method": "POST", "endpoint": "/api/v1/generate", "resolved": True,
        "docs_url": "https://docs.kie.ai/suno-api/generate-music.md", "models": [],
        "summary": "Suno music generation with model, lyrics/custom mode, style, title, voice and generation controls.",
        "example_body": {"prompt": "", "customMode": False, "instrumental": False, "model": "V5_5", "style": "", "title": "", "negativeTags": "", "vocalGender": "", "styleWeight": 0.65, "weirdnessConstraint": 0.65, "audioWeight": 0.65, "personaId": "", "personaModel": "", "duration": 120},
        "parameter_hints": {"model": {"type": "string", "required": True, "enum": ["V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5", "V5_5"]}},
    },
    {
        "label": "Veo3.1 API • Generate Veo3.1 Video",
        "title": "Generate Veo3.1 Video", "family": "Veo3.1 API",
        "method": "POST", "endpoint": "/api/v1/veo/generate", "resolved": True,
        "docs_url": "https://docs.kie.ai/veo3-api/generate-veo-3-video.md", "models": [],
        "summary": "Veo 3.1 text, first/last-frame and reference video generation.",
        "example_body": {"prompt": "", "imageUrls": [], "model": "veo3_fast", "watermark": "", "aspect_ratio": "16:9", "enableFallback": True, "enableTranslation": True, "generationType": "TEXT_2_VIDEO"},
    },
]



def generated_catalog_path() -> Path:
    return settings_path().parent / "catalog.generated.json"


def bundled_catalog_path() -> Path:
    """Catalog shipped with the node pack, available before any network sync."""
    return Path(__file__).resolve().parents[1] / "models" / "catalog.json"


def _read_catalog_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _operation_key(op: dict[str, Any]) -> str:
    return str(op.get("docs_url") or op.get("label") or op.get("title") or "").strip()


def _operation_quality(op: dict[str, Any]) -> tuple[int, int, int, int]:
    hints = op.get("parameter_hints") if isinstance(op.get("parameter_hints"), dict) else {}
    body = op.get("example_body") if isinstance(op.get("example_body"), dict) else {}
    return (
        len(hints),
        len(body),
        int(bool(op.get("method") and op.get("endpoint"))),
        len(op.get("models") or []),
    )


def _merge_catalogs(bundled: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    """Merge live discoveries without allowing stale cache to erase richer specs."""
    merged = dict(bundled)
    merged.update({k: v for k, v in generated.items() if k not in {"models", "operations"}})

    models: dict[str, dict[str, Any]] = {}
    for source in (bundled.get("models") or [], generated.get("models") or []):
        for model in source:
            model_id = str(model.get("model") or "").strip()
            if model_id:
                models[model_id] = {**models.get(model_id, {}), **dict(model)}

    operations: dict[str, dict[str, Any]] = {}
    for op in bundled.get("operations") or []:
        key = _operation_key(op)
        if key:
            operations[key] = dict(op)
    for candidate in generated.get("operations") or []:
        key = _operation_key(candidate)
        if not key:
            continue
        current = operations.get(key)
        if current is None or _operation_quality(candidate) >= _operation_quality(current):
            operations[key] = dict(candidate)

    merged["models"] = sorted(models.values(), key=lambda m: (str(m.get("family")), str(m.get("name")), str(m.get("model"))))
    merged["operations"] = sorted(operations.values(), key=lambda op: str(op.get("label") or op.get("title")))
    merged["catalog_merge"] = "bundled schemas plus live discoveries"
    return merged


def load_catalog() -> dict[str, Any]:
    bundled = _read_catalog_file(bundled_catalog_path())
    generated = _read_catalog_file(generated_catalog_path())
    if bundled and generated:
        return _merge_catalogs(bundled, generated)
    if bundled:
        return bundled
    if generated:
        return generated
    return {"schema_version": 3, "generated_at": 0, "models": SEED_MODELS, "operations": SEED_OPERATIONS, "deep_sync_complete": False}


def _write_catalog(payload: dict[str, Any]) -> None:
    path = generated_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _CATALOG_WRITE_LOCK:
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)


def catalog_age_seconds() -> float:
    generated = float(load_catalog().get("generated_at") or 0)
    return max(0.0, time.time() - generated) if generated else 10**12


def model_options() -> list[str]:
    models = load_catalog().get("models") or []
    ids = sorted({
        str(m.get("model") or "").strip()
        for m in models
        if str(m.get("model") or "").strip() and str(m.get("transport") or "market_task") == "market_task"
    })
    return ids or [m["model"] for m in SEED_MODELS]


def operation_options() -> list[str]:
    ops = load_catalog().get("operations") or []
    labels = [str(op.get("label") or "").strip() for op in ops if str(op.get("label") or "").strip()]
    return labels or ["Custom endpoint"]


def operation_by_label(label: str) -> dict[str, Any] | None:
    for op in load_catalog().get("operations") or []:
        if op.get("label") == label:
            return op
    return None


def _operation_label(prefix: str, title: str) -> str:
    family = prefix or "KIE API"
    return f"{family} • {title}"


def _parse_llms_index(text: str) -> list[dict[str, str]]:
    # Only the English API Docs section; quickstarts/callback documentation above
    # it are not callable operations. The Chinese duplicate section is excluded.
    if "## API Docs" in text:
        text = text.split("## API Docs", 1)[1]
    if "https://docs.kie.ai/cn/" in text:
        text = text.split("https://docs.kie.ai/cn/", 1)[0]

    entries: list[dict[str, str]] = []
    rx = re.compile(r"^-\s*(?P<prefix>.*?)\[(?P<title>[^\]]+)\]\((?P<url>https://docs\.kie\.ai/[^)]+\.md)\):", re.M)
    for match in rx.finditer(text):
        url = match.group("url")
        if "/cn/" in url:
            continue
        prefix = re.sub(r"\s+", " ", match.group("prefix")).strip(" >")
        entries.append({"prefix": prefix, "title": match.group("title").strip(), "url": url})
    return entries


def _extract_endpoint(text: str) -> tuple[str, str]:
    host = r"https://(?:api\.kie\.ai|kieai\.redpandaai\.co)"
    relative = r"/(?:api|v1|codex|claude|gemini|chat|openai)/[^\s`\"')]+"
    # Apidog markdown normally renders method and path/URL together or on adjacent lines.
    block = re.search(
        rf"(?mi)^\s*(GET|POST|PUT|PATCH|DELETE)\s*$[\r\n]+\s*({host}[^\s`\"')]+|{relative})\s*$",
        text,
    )
    if block:
        return block.group(1).upper(), block.group(2).rstrip(".,")

    inline = re.search(
        # HTML docs commonly render the method and path as adjacent text
        # (for example, POST/api/v1/jobs/createTask), while Markdown inserts
        # whitespace. Accept both representations.
        rf"\b(GET|POST|PUT|PATCH|DELETE)\s*({host}[^\s`\"')]+|{relative})",
        text,
        re.I,
    )
    if inline:
        return inline.group(1).upper(), inline.group(2).rstrip(".,")

    # The current Apidog pages embed the page's OpenAPI specification in the
    # HTML. Once converted to plain text it appears as YAML under `paths:`.
    openapi = re.search(
        r"(?is)\bpaths:\s*(/[^:\s]+):\s*(get|post|put|patch|delete):",
        text,
    )
    if openapi:
        return openapi.group(2).upper(), openapi.group(1)

    # cURL fallback. --request/-X wins; a request carrying data/form is POST.
    curl = re.search(rf"curl[^\n]*?[\"']({host}[^\"']+)[\"']", text, re.I)
    if curl:
        method_match = re.search(r"(?:--request|-X)\s+(GET|POST|PUT|PATCH|DELETE)", text, re.I)
        method = method_match.group(1).upper() if method_match else (
            "POST" if re.search(r"--(?:data(?:-raw)?|form)\s", text, re.I) else "GET"
        )
        return method, curl.group(1)
    return "", ""


def _split_endpoint_query(endpoint: str) -> tuple[str, dict[str, Any]]:
    raw = str(endpoint or "").strip()
    if not raw or "?" not in raw:
        return raw, {}
    if raw.startswith("http"):
        parts = urlsplit(raw)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        clean = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return clean, query
    path, query_text = raw.split("?", 1)
    return path, dict(parse_qsl(query_text, keep_blank_values=True))


def _extract_example_query(text: str, endpoint_query: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(endpoint_query or {})
    # Preserve documented sample values; they provide useful widget defaults and,
    # more importantly, reveal query fields such as taskId/status IDs.
    for url in re.findall(r"https://(?:api\.kie\.ai|kieai\.redpandaai\.co)[^\s`\"')]+", text):
        if "?" not in url:
            continue
        try:
            for k, v in parse_qsl(urlsplit(url.rstrip(".,")).query, keep_blank_values=True):
                result.setdefault(k, v)
        except Exception:
            pass
    return result


def _extract_path_params(endpoint: str) -> list[str]:
    names = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(endpoint or ""))
    names += re.findall(r"(?<!https):([A-Za-z_][A-Za-z0-9_]*)", str(endpoint or ""))
    return list(dict.fromkeys(names))


def _extract_models(text: str) -> list[str]:
    # Request examples are authoritative for the node's model. Response examples
    # sometimes echo unrelated/fallback model names, so stop before Responses.
    request_text = re.split(r"(?mi)^##\s+Responses?\b", text, maxsplit=1)[0]
    values = re.findall(r'["\']model["\']\s*:\s*["\']([^"\']+)["\']', request_text)
    values += re.findall(r"\bmodel\s*=\s*[\"']([^\"']+)[\"']", request_text)
    cleaned: list[str] = []
    for value in values:
        value = value.strip()
        if value and not value.startswith(("<", "{", "$")) and value not in cleaned:
            cleaned.append(value)
    return cleaned


def _operation_model_variants(doc: dict[str, Any]) -> list[str]:
    """Explicit model IDs plus model-enum versions documented by KIE."""
    values = [str(x).strip() for x in (doc.get("models") or []) if str(x).strip()]
    model_hint = (doc.get("parameter_hints") or {}).get("model") or {}
    enum_values = model_hint.get("enum") or model_hint.get("options") or []
    if isinstance(enum_values, str):
        enum_values = [x.strip() for x in enum_values.split(",")]
    for value in enum_values:
        value = str(value).strip()
        if value and value not in values:
            values.append(value)
    body = doc.get("example_body") if isinstance(doc.get("example_body"), dict) else {}
    body_model = str(body.get("model") or "").strip()
    if body_model and body_model not in values:
        values.append(body_model)
    return values


def _extract_example_body(text: str) -> dict[str, Any] | None:
    # KIE/Apidog pages generally expose a cURL --data JSON example. This is only
    # a convenience preview; callers can always provide their own JSON body.
    patterns = [
        r"--data(?:-raw)?\s+'(\{.*?\})'",
        r'--data(?:-raw)?\s+"(\{.*?\})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.S | re.I)
        if not match:
            continue
        candidate = match.group(1).replace("\\\n", "").strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _hint_from_schema(schema: dict[str, Any], *, required: bool) -> dict[str, Any]:
    """Convert an OpenAPI property into compact, ComfyUI-friendly metadata."""
    hint: dict[str, Any] = {
        "type": str(schema.get("type") or "string"),
        "required": required,
        "description": str(schema.get("description") or ""),
    }
    for key in ("enum", "default", "minimum", "maximum", "minLength", "maxLength", "format"):
        if key in schema:
            hint[key] = schema[key]
    examples = schema.get("examples")
    if "default" not in hint and isinstance(examples, list) and examples:
        hint["default"] = examples[0]
    if isinstance(schema.get("items"), dict):
        hint["items"] = dict(schema["items"])
    return hint


def _extract_openapi_request(text: str, endpoint: str, method: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the OpenAPI YAML embedded by KIE's current Apidog HTML pages.

    Returns an example request body and field hints. For Market createTask APIs,
    the useful controls live in `input`, so the transport envelope is removed.
    """
    if yaml is None:
        return {}, {}
    start = text.find("openapi:")
    if start < 0:
        return {}, {}
    try:
        document = yaml.safe_load(text[start:].split("```", 1)[0])
        paths = document.get("paths") if isinstance(document, dict) else {}
        operation = (paths.get(endpoint) or {}).get(str(method or "post").lower())
        content = ((operation or {}).get("requestBody") or {}).get("content") or {}
        media = content.get("application/json") or next(iter(content.values()), {})
        schema = media.get("schema") if isinstance(media, dict) else {}
        if not isinstance(schema, dict):
            return {}, {}
        example = media.get("example") if isinstance(media.get("example"), dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = set(schema.get("required") or [])

        # KIE Market APIs wrap model controls inside input. Keep that wrapper out
        # of the visual node while retaining the original request example.
        if endpoint == "/api/v1/jobs/createTask" and isinstance(properties.get("input"), dict):
            input_schema = properties["input"]
            properties = input_schema.get("properties") or {}
            required = set(input_schema.get("required") or [])
            example = example.get("input") if isinstance(example.get("input"), dict) else {}

        hints = {
            str(name): _hint_from_schema(value, required=str(name) in required)
            for name, value in properties.items()
            if isinstance(value, dict)
        }
        return dict(example), hints
    except Exception:
        return {}, {}



def _parse_hint_options(description: str) -> list[str]:
    desc = str(description or "")
    values: list[str] = []
    # Backticked and quoted values are common in KIE/Apidog option descriptions.
    for value in re.findall(r"`([^`]{1,60})`|\"([^\"]{1,60})\"|'([^']{1,60})'", desc):
        item = next((x for x in value if x), "").strip()
        if item and item.lower() not in {"string", "boolean", "integer", "number", "array", "object"}:
            values.append(item)
    # Also support explicit "Options: a, b, c" prose.
    m = re.search(r"(?i)(?:options?|allowed values?|enum)\s*[:：]\s*([^.;\n]+)", desc)
    if m:
        for item in re.split(r"\s*[,/]\s*|\s+or\s+", m.group(1)):
            item = item.strip(" `\"'")
            if item: values.append(item)
    # Avoid interpreting arbitrary prose as an enum.
    values = list(dict.fromkeys(values))
    return values if 1 < len(values) <= 24 else []


def _extract_parameter_hints(text: str) -> dict[str, dict[str, Any]]:
    """Best-effort metadata from KIE/Apidog request/parameter Markdown tables.

    Only tables whose first header cell is Parameter/Name/Field/Property are
    treated as request fields. This deliberately ignores model-limit tables and
    response schemas that would otherwise become bogus ComfyUI inputs.
    """
    hints: dict[str, dict[str, Any]] = {}
    text = text.split("## Responses", 1)[0]
    lines = text.splitlines()
    active_table = False
    for raw in lines:
        if "|" not in raw:
            if raw.strip() and active_table:
                active_table = False
            continue
        cells = [re.sub(r"[`*]", "", c).strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0].strip()
        first_low = first.lower()
        if first_low in {"parameter", "parameter name", "name", "field", "property", "param"}:
            active_table = True
            continue
        if all(re.fullmatch(r"[-: ]*", c or "") for c in cells):
            continue
        if not active_table:
            continue
        name = first
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", name):
            continue

        typ = ""
        required = False
        desc_cells: list[str] = []
        for cell in cells[1:]:
            low = cell.lower()
            if not typ and re.search(r"\b(string|boolean|bool|integer|int|number|float|array|object|json|file)\b", low):
                typ = low
                continue
            if low in {"yes", "required", "true", "y"}:
                required = True; continue
            if low in {"no", "optional", "false", "n"}:
                continue
            desc_cells.append(cell)
        desc = re.sub(r"\s+", " ", " | ".join(x for x in desc_cells if x)).strip()
        hint: dict[str, Any] = {"type": typ, "required": required, "description": desc}
        enums = _parse_hint_options(desc)
        if enums: hint["enum"] = enums
        default_match = re.search(r"(?i)default(?: value)?\s*[:=]?\s*`?([A-Za-z0-9_.:+-]+)`?", desc)
        if default_match:
            raw_default = default_match.group(1)
            if raw_default.lower() in {"true", "false"}: hint["default"] = raw_default.lower() == "true"
            elif re.fullmatch(r"-?\d+", raw_default): hint["default"] = int(raw_default)
            elif re.fullmatch(r"-?\d+\.\d+", raw_default): hint["default"] = float(raw_default)
            else: hint["default"] = raw_default
        hints[name] = hint
    return hints


def _extract_text_summary(text: str) -> str:
    # Keep a short, safe plain-text excerpt for node DESCRIPTION tooltips.
    body = re.sub(r"```.*?```", " ", text, flags=re.S)
    body = re.sub(r"[#>*`|]", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:700]

def _normalize_endpoint(endpoint: str) -> str:
    endpoint = str(endpoint or "").strip()
    if endpoint.startswith("https://api.kie.ai"):
        return endpoint[len("https://api.kie.ai"):]
    # The upload API has its own KIE-owned base, so preserve it as an absolute URL.
    return endpoint


def _fetch_doc(session: requests.Session, entry: dict[str, str]) -> dict[str, Any]:
    try:
        response = session.get(entry["url"], timeout=DOC_TIMEOUT)
        response.raise_for_status()
        text = response.text
        # KIE migrated its public docs from Markdown pages to Apidog-rendered HTML.
        # Convert the visible document back to plain text before applying the same
        # endpoint, model, sample-body and parameter extractors.
        if "<html" in text[:2048].lower():
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    except Exception as exc:
        return {**entry, "error": str(exc), "method": "", "endpoint": "", "models": []}
    method, raw_endpoint = _extract_endpoint(text)
    clean_endpoint, endpoint_query = _split_endpoint_query(raw_endpoint)
    endpoint = _normalize_endpoint(clean_endpoint)
    schema_body, schema_hints = _extract_openapi_request(text, endpoint, method)
    sample_body = schema_body or _extract_example_body(text)
    table_hints = _extract_parameter_hints(text)
    table_hints.update(schema_hints)
    return {
        **entry,
        "method": method,
        "endpoint": endpoint,
        "models": _extract_models(text),
        "example_body": sample_body,
        "example_query": _extract_example_query(text, endpoint_query),
        "path_params": _extract_path_params(endpoint),
        "parameter_hints": table_hints,
        "summary": _extract_text_summary(text),
    }


def _skeleton_operation(entry: dict[str, str]) -> dict[str, Any]:
    return {
        "label": _operation_label(entry.get("prefix") or "", entry.get("title") or "KIE API"),
        "title": entry.get("title") or "",
        "family": entry.get("prefix") or "KIE API",
        "method": "",
        "endpoint": "",
        "docs_url": entry.get("url") or "",
        "resolved": False,
    }


def _enrich_operation(op: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    updated = dict(op)
    if doc.get("method"):
        updated["method"] = doc.get("method")
    if doc.get("endpoint"):
        updated["endpoint"] = doc.get("endpoint")
    if doc.get("example_body"):
        updated["example_body"] = doc.get("example_body")
    if doc.get("example_query"):
        updated["example_query"] = doc.get("example_query")
    if doc.get("path_params"):
        updated["path_params"] = doc.get("path_params")
    if doc.get("models"):
        updated["models"] = list(doc.get("models") or [])
    if doc.get("parameter_hints"):
        updated["parameter_hints"] = doc.get("parameter_hints")
    if doc.get("summary"):
        updated["summary"] = doc.get("summary")
    if doc.get("method") and doc.get("endpoint"):
        updated["resolved"] = True

    is_market_doc = "/market/" in str(doc.get("url") or "")
    is_market_task = str(doc.get("endpoint") or "") == "/api/v1/jobs/createTask"
    if is_market_doc and not is_market_task and len(doc.get("models") or []) == 1:
        updated["default_model"] = (doc.get("models") or [""])[0]
    if doc.get("error"):
        updated["last_error"] = str(doc.get("error"))
    else:
        updated.pop("last_error", None)
    return updated


def resolve_operation(label: str) -> dict[str, Any] | None:
    """Resolve a selected operation on-demand if its docs failed during catalog sync."""
    op = operation_by_label(label)
    if not op:
        return None
    if op.get("method") and op.get("endpoint"):
        return op
    docs_url = str(op.get("docs_url") or "")
    if not docs_url:
        return op

    session = requests.Session()
    session.headers.update({"User-Agent": "ComfyUI-KIE-Nodes-Next/0.3 operation-resolver"})
    entry = {"prefix": str(op.get("family") or ""), "title": str(op.get("title") or ""), "url": docs_url}
    doc = _fetch_doc(session, entry)
    updated = _enrich_operation(op, doc)
    if not updated.get("method") or not updated.get("endpoint"):
        return updated

    catalog = load_catalog()
    operations = []
    for existing in catalog.get("operations") or []:
        operations.append(updated if existing.get("label") == label else existing)

    # Opportunistically remember every explicit model/version, not only Market
    # createTask IDs. Direct APIs such as Suno/Veo/LLMs also deserve individual
    # model inventory entries and individual ComfyUI nodes.
    models = {str(m.get("model")): dict(m) for m in (catalog.get("models") or []) if m.get("model")}
    for model in _operation_model_variants(doc):
        models[model] = {
            "name": doc.get("title") or model,
            "model": model,
            "family": doc.get("prefix") or "KIE API",
            "docs_url": docs_url,
            "method": doc.get("method") or "",
            "endpoint": doc.get("endpoint") or "",
            "transport": "market_task" if doc.get("endpoint") == "/api/v1/jobs/createTask" else "direct",
        }

    catalog["operations"] = operations
    catalog["models"] = sorted(models.values(), key=lambda m: (str(m.get("family")), str(m.get("name")), str(m.get("model"))))
    _write_catalog(catalog)
    return updated


def sync_catalog(*, max_workers: int = 8, index_only: bool = False) -> dict[str, Any]:
    if not _SYNC_LOCK.acquire(blocking=False):
        return {"ok": True, "busy": True, **catalog_summary()}
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "ComfyUI-KIE-Nodes-Next/0.3 catalog-sync"})
        index = session.get(LLMS_URL, timeout=DOC_TIMEOUT)
        index.raise_for_status()
        entries = _parse_llms_index(index.text)

        # Every API page enters the catalog before enrichment. A transient fetch
        # failure therefore cannot make an official KIE API disappear from ComfyUI.
        operations_by_url: dict[str, dict[str, Any]] = {
            entry["url"]: _skeleton_operation(entry) for entry in entries
        }

        if index_only:
            existing = load_catalog()
            existing_models = existing.get("models") or SEED_MODELS
            payload = {
                "schema_version": 3,
                "generated_at": int(time.time()),
                "source": LLMS_URL,
                "deep_sync_complete": False,
                "documents_indexed": len(entries),
                "documents_scanned": 0,
                "documents_failed": 0,
                "models": existing_models,
                "operations": sorted(operations_by_url.values(), key=lambda op: str(op.get("label"))),
            }
            _write_catalog(payload)
            return {"ok": True, **catalog_summary()}

        docs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 12))) as pool:
            futures = [pool.submit(_fetch_doc, session, entry) for entry in entries]
            for future in as_completed(futures):
                docs.append(future.result())

        models: dict[str, dict[str, Any]] = {m["model"]: dict(m) for m in SEED_MODELS}
        for doc in docs:
            url = str(doc.get("url") or "")
            if url in operations_by_url:
                operations_by_url[url] = _enrich_operation(operations_by_url[url], doc)

            endpoint = str(doc.get("endpoint") or "")
            is_market_task = endpoint == "/api/v1/jobs/createTask"
            for model in _operation_model_variants(doc):
                models[model] = {
                    "name": doc.get("title") or model,
                    "model": model,
                    "family": doc.get("prefix") or "KIE API",
                    "docs_url": url,
                    "method": doc.get("method") or "",
                    "endpoint": endpoint,
                    "transport": "market_task" if is_market_task else "direct",
                }

        payload = {
            "schema_version": 3,
            "generated_at": int(time.time()),
            "source": LLMS_URL,
            "deep_sync_complete": True,
            "documents_indexed": len(entries),
            "documents_scanned": len(docs),
            "documents_failed": sum(1 for d in docs if d.get("error")),
            "models": sorted(models.values(), key=lambda m: (str(m.get("family")), str(m.get("name")), str(m.get("model")))),
            "operations": sorted(operations_by_url.values(), key=lambda op: str(op.get("label"))),
        }
        _write_catalog(payload)
        return {"ok": True, **catalog_summary()}
    finally:
        _SYNC_LOCK.release()


def catalog_summary() -> dict[str, Any]:
    catalog = load_catalog()
    operations = catalog.get("operations") or []
    return {
        "generated_at": catalog.get("generated_at") or 0,
        "age_seconds": int(catalog_age_seconds()),
        "models": len(catalog.get("models") or []),
        "operations": len(operations),
        "operations_resolved": sum(1 for op in operations if op.get("method") and op.get("endpoint")),
        "documents_indexed": int(catalog.get("documents_indexed") or 0),
        "documents_scanned": int(catalog.get("documents_scanned") or 0),
        "documents_failed": int(catalog.get("documents_failed") or 0),
        "deep_sync_complete": bool(catalog.get("deep_sync_complete")),
        "path": str(generated_catalog_path()),
    }

