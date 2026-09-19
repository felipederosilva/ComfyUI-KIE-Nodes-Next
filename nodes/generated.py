from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from ..kie.catalog import load_catalog, resolve_operation
from ..kie.client import KIEAPIError, KIEClient, pretty_json
from ..kie.helpers import make_client, parse_object_json
KIE_GENERATED_BUILD = "0.4.3"

from ..kie.media import (
    download_audio_object,
    download_image_tensor,
    download_video_object,
    upload_audio,
    upload_image_batch,
    video_to_temp_file,
)

# ---------------------------- presentation ---------------------------------

_VENDOR_NAMES = {
    "Bytedance": "ByteDance",
    "Google": "Google",
    "GPT Image": "OpenAI",
    "GPT": "OpenAI",
    "Codex": "OpenAI",
    "Claude": "Claude",
    "Flux-2": "Black Forest Labs",
    "Grok Imagine": "xAI",
    "Grok": "xAI",
    "MiniMax H3": "MiniMax",
}


def _clean_family(family: str) -> list[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in str(family or "").split(">") if p.strip()]


def _series_bucket(root: str, vendor: str, op: dict[str, Any]) -> str:
    combined = " ".join([
        str(op.get("family") or ""), str(op.get("title") or ""),
        " ".join(str(x) for x in (op.get("models") or [])),
        str(op.get("default_model") or ""),
    ]).lower()

    if root == "Video" and vendor == "ByteDance":
        return "Seedance" if "seedance" in combined else "V1"
    if root == "Image" and vendor == "ByteDance":
        return "Seedream"
    if vendor == "Google":
        if "nano banana" in combined or "nano-banana" in combined: return "Nano Banana"
        if "imagen" in combined: return "Imagen"
        if root == "LLM" and "gemini" in combined: return "Gemini"
        if root == "Video" and "veo" in combined: return "Veo"
    if vendor == "OpenAI":
        if "gpt image" in combined or "gpt-image" in combined: return "GPT Image"
        if "4o image" in combined: return "4o Image"
        if "codex" in combined: return "Codex"
        if root == "LLM": return "GPT"
    if vendor == "Claude":
        for series in ("Opus", "Sonnet", "Haiku", "Fable"):
            if series.lower() in combined: return series
        return "Claude"
    if vendor == "xAI":
        return "Grok Imagine" if "imagine" in combined else "Grok"
    if vendor == "Black Forest Labs":
        return "Flux Kontext" if "kontext" in combined else "Flux 2"
    if root == "Audio" and vendor == "ElevenLabs":
        if "isolation" in combined: return "Audio Isolation"
        if "dialogue" in combined: return "Dialogue"
        if "speech" in combined or "tts" in combined: return "Text to Speech"
    if root == "Audio" and vendor == "Suno":
        if "generate music" in combined or "music generation" in combined: return "Music Generation"
        if "lyrics" in combined: return "Lyrics"
        if "stem" in combined or "separation" in combined: return "Stems"
    if root == "Audio" and vendor == "Google" and ("speech" in combined or "tts" in combined):
        return "Gemini TTS"
    if root == "Video" and vendor == "Google" and "gemini omni" in combined:
        return "Gemini Omni"
    if "kling" in combined: return "Kling"
    if "wan" in combined: return "Wan"
    if "qwen" in combined: return "Qwen"
    if "ideogram" in combined: return "Ideogram"
    if "recraft" in combined: return "Recraft"
    if "topaz" in combined: return "Topaz"
    if "hailuo" in combined: return "Hailuo"
    if "pixverse" in combined: return "PixVerse"
    if "minimax" in combined or "hailuo" in combined: return "MiniMax"
    return ""


def category_for(op: dict[str, Any]) -> str:
    family = str(op.get("family") or "")
    parts = _clean_family(family)
    if not parts:
        return "KIE Next/Utility"

    head = parts[0].lower()
    tail = parts[1:] if len(parts) > 1 else []
    combined = f"{family} {op.get('title','')} {' '.join(str(x) for x in (op.get('models') or []))}".lower()

    if head.startswith("suno"):
        title = str(op.get("title") or "").lower()
        subsection = tail[-1] if tail else ("Music Generation" if "generate music" in title else "Generation")
        return f"KIE Next/Audio/Suno/{subsection}"
    if head.startswith("veo") or "veo3" in head:
        return "KIE Next/Video/Google/Veo"
    if "runway" in combined:
        return "KIE Next/Video/Runway/Aleph" if "aleph" in combined else "KIE Next/Video/Runway"
    if "file" in head or "common" in head or "webhook" in head:
        return "KIE Next/Utility"

    if "image" in head:
        root = "Image"
    elif "video" in head:
        root = "Video"
    elif "music" in head or "audio" in head:
        root = "Audio"
    elif "chat" in head or "llm" in head:
        root = "LLM"
    else:
        root = "Utility"

    raw_vendor = tail[0] if tail else ""
    raw_vendor = re.sub(r"\s+API$", "", raw_vendor, flags=re.I).strip()
    vendor = _VENDOR_NAMES.get(raw_vendor, raw_vendor)

    # Product families whose public brand/provider is clearer than the docs heading.
    if root == "Image" and raw_vendor == "Seedream": vendor = "ByteDance"
    if raw_vendor in {"GPT Image", "4o Image"}: vendor = "OpenAI"
    if raw_vendor in {"Grok Imagine", "Grok"}: vendor = "xAI"
    if raw_vendor == "Flux-2" or "flux kontext" in combined: vendor = "Black Forest Labs"
    if root == "LLM" and raw_vendor.startswith("Gemini"): vendor = "Google"
    if raw_vendor == "Gemini Omni": vendor = "Google"
    if root == "Audio" and raw_vendor == "Gemini": vendor = "Google"
    if root == "LLM" and (raw_vendor.startswith("GPT") or raw_vendor.startswith("Codex")): vendor = "OpenAI"

    if not vendor:
        return f"KIE Next/{root}"
    series = _series_bucket(root, vendor, op)
    if series and series.lower() != vendor.lower():
        return f"KIE Next/{root}/{vendor}/{series}"
    return f"KIE Next/{root}/{vendor}"

def kind_for(op: dict[str, Any]) -> str:
    family = str(op.get("family") or "").lower()
    title = str(op.get("title") or "").lower()
    if "chat" in family:
        return "llm"
    if "lyrics" in family or "lyrics" in title:
        return "text"
    if "music video" in family or "music video" in title:
        return "video"
    if "image" in family or "4o image" in family or "flux kontext" in family:
        return "image"
    if "video" in family or "veo" in family or "runway" in family:
        return "video"
    if "music" in family or "suno" in family or "elevenlabs" in family or "speech" in title or "audio" in title:
        return "audio"
    return "utility"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value[:90] or "KIE"


def display_name_for(op: dict[str, Any], model: str = "") -> str:
    title = re.sub(r"\s+", " ", str(op.get("title") or model or "KIE Model")).strip()
    # Folder hierarchy already communicates the provider; remove repetitive prefixes
    # so menus read "Seedance 2.5" instead of "Bytedance Seedance 2.5".
    for prefix in ("Bytedance ", "Google - ", "Google "):
        if title.lower().startswith(prefix.lower()) and len(title) > len(prefix):
            candidate = title[len(prefix):].strip()
            if candidate:
                title = candidate
                break
    title = re.sub(r"^bytedance[- ]", "", title, flags=re.I)
    seedance = re.fullmatch(r"seedance[- ](\d+)(?:[.-](\d+))?", title, flags=re.I)
    if seedance:
        major, minor = seedance.groups()
        title = f"Seedance {major}.{minor or '0'}"
    return title


def node_id_for(op: dict[str, Any], model: str = "") -> str:
    stable = str(op.get("docs_url") or op.get("label") or op.get("title") or "") + "|" + model
    digest = hashlib.sha1(stable.encode("utf-8")).hexdigest()[:8]
    label = model or str(op.get("title") or "KIE")
    return f"KIE_Next_{_slug(label)}_{digest}"


# ------------------------------ widget inference ----------------------------

_ASPECTS = ["auto", "16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"]
_RESOLUTIONS = ["480p", "540p", "720p", "1080p", "1K", "2K", "4K"]
_IMAGE_SIZES = ["square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
_OUTPUT_FORMATS = ["png", "jpg", "jpeg", "webp"]
_SUNO_MODELS = ["V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5", "V5_5"]
_VEO_MODELS = ["veo3", "veo3_fast", "veo3_lite"]
_REASONING = ["low", "medium", "high", "xhigh"]


def _dedupe_default(default: str, values: list[str]) -> list[str]:
    result = []
    if default and default not in result:
        result.append(default)
    for v in values:
        if v not in result:
            result.append(v)
    return result


def _is_image_field(name: str) -> bool:
    n = name.lower()
    if n in {"first_frame_url", "last_frame_url", "firstframeurl", "lastframeurl", "input_urls"}:
        return True
    return "image" in n and ("url" in n or n in {"images", "image_input", "imageurls"})


def _is_video_field(name: str) -> bool:
    n = name.lower()
    return "video" in n and ("url" in n or n in {"video", "videos"})


def _is_audio_field(name: str) -> bool:
    n = name.lower()
    return ("audio" in n or "uploadurl" in n) and ("url" in n or n in {"audio", "audios", "uploadurllist"})


def _required_media(title: str, name: str) -> bool:
    t, n = title.lower(), name.lower()
    if "image to video" in t or "image-to-video" in t or "image to image" in t or "image-to-image" in t or " edit" in t:
        return _is_image_field(n) and "reference" not in n and "last" not in n
    if "from audio" in t or "speech to video" in t or "audio isolation" in t:
        return _is_audio_field(n)
    return False



def _is_plural_media_field(name: str, example: Any = None) -> bool:
    n = name.lower()
    return isinstance(example, list) or "urls" in n or n.endswith("list") or n.endswith("s")


def _media_aliases(name: str, example: Any = None) -> list[tuple[str, str, bool]]:
    """Friendly native sockets for plural VIDEO/AUDIO URL arrays.

    IMAGE already supports batches naturally in ComfyUI. VIDEO/AUDIO do not have a
    universal batch socket, so KIE Next exposes a few numbered native inputs rather
    than forcing users to paste URL JSON.
    """
    n = name.lower()
    if _is_video_field(name) and _is_plural_media_field(name, example):
        base = re.sub(r"_?urls?$|_?list$", "", name, flags=re.I).rstrip("_") or "video"
        return [(f"{base}_{i}", "VIDEO", False) for i in range(1, 4)]
    if _is_audio_field(name) and _is_plural_media_field(name, example):
        if n == "uploadurllist":
            return [("audio_1", "AUDIO", True), ("audio_2", "AUDIO", True)]
        base = re.sub(r"_?urls?$|_?list$", "", name, flags=re.I).rstrip("_") or "audio"
        return [(f"{base}_{i}", "AUDIO", False) for i in range(1, 4)]
    return []

def _hint_default(hint: dict[str, Any]) -> Any:
    if "default" in hint:
        return hint.get("default")
    typ = str(hint.get("type") or "").lower()
    if "bool" in typ: return False
    if any(x in typ for x in ("int", "number", "float", "double")): return 0
    if "array" in typ or "list" in typ: return []
    if "object" in typ or "json" in typ: return {}
    return ""


def _enum_from_hint(hint: dict[str, Any]) -> list[str]:
    values = hint.get("enum") or hint.get("options") or []
    if isinstance(values, str): values = [x.strip() for x in values.split(",")]
    return [str(x) for x in values if str(x).strip()]


def _scalar_widget(name: str, value: Any, op: dict[str, Any]):
    n = name.lower()
    hint = (op.get("parameter_hints") or {}).get(name) or {}
    desc = str(hint.get("description") or "")
    hinted_enum = _enum_from_hint(hint)
    if value is None:
        value = _hint_default(hint)

    common = {"tooltip": desc} if desc else {}
    if hinted_enum:
        default = str(value) if value not in (None, "") else hinted_enum[0]
        return (_dedupe_default(default, hinted_enum), {"default": default, **common})
    schema_type = str(hint.get("type") or "").lower()
    if schema_type in {"integer", "int"}:
        default = int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else int(hint.get("default") or 0)
        return ("INT", {
            "default": default,
            "min": int(hint.get("minimum", -2147483648)),
            "max": int(hint.get("maximum", 2147483647)),
            "step": 1,
            **common,
        })
    if schema_type in {"number", "float", "double"}:
        default = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float(hint.get("default") or 0.0)
        return ("FLOAT", {
            "default": default,
            "min": float(hint.get("minimum", -10000.0)),
            "max": float(hint.get("maximum", 10000.0)),
            "step": 0.01,
            **common,
        })
    if schema_type in {"boolean", "bool"}:
        return ("BOOLEAN", {"default": bool(value if value is not None else hint.get("default", False)), **common})
    if n in {"aspect_ratio", "aspectratio"} and isinstance(value, str):
        return (_dedupe_default(value or "auto", _ASPECTS), {"default": value or "auto", **common})
    if n in {"resolution", "image_resolution", "resolution_type"} and isinstance(value, str):
        return (_dedupe_default(value or "720p", _RESOLUTIONS), {"default": value or "720p", **common})
    if n in {"output_format", "outputformat"} and isinstance(value, str):
        return (_dedupe_default(value or "png", _OUTPUT_FORMATS), {"default": value or "png", **common})
    if n == "image_size" and isinstance(value, str):
        return (_dedupe_default(value or "square_hd", _IMAGE_SIZES), {"default": value or "square_hd", **common})
    if n == "model" and isinstance(value, str):
        family = str(op.get("family") or "").lower()
        values = _SUNO_MODELS if "suno" in family else (_VEO_MODELS if "veo" in family else [value])
        return (_dedupe_default(value, values), {"default": value, **common})
    if n in {"generationtype", "generation_type"} and isinstance(value, str):
        vals = ["TEXT_2_VIDEO", "FIRST_AND_LAST_FRAMES_2_VIDEO", "REFERENCE_2_VIDEO"]
        return (_dedupe_default(value, vals), {"default": value, **common})
    if n in {"vocalgender", "vocal_gender"} and isinstance(value, str):
        return (_dedupe_default(value, ["m", "f"]), {"default": value, **common})
    if isinstance(value, bool):
        return ("BOOLEAN", {"default": value, **common})
    if isinstance(value, int) and not isinstance(value, bool):
        opts: dict[str, Any] = {"default": value, "step": 1, **common}
        if n == "seed": opts.update({"min": -1, "max": 2147483647})
        elif "duration" in n: opts.update({"min": 1, "max": 600})
        elif "token" in n: opts.update({"min": 1, "max": 131072})
        elif n in {"safetytolerance", "safety_tolerance"}: opts.update({"min": 0, "max": 6})
        else: opts.update({"min": -2147483648, "max": 2147483647})
        return ("INT", opts)
    if isinstance(value, float):
        opts = {"default": value, "step": 0.01 if any(k in n for k in ("weight", "constraint")) else 0.05, **common}
        if any(k in n for k in ("weight", "constraint")): opts.update({"min": 0.0, "max": 1.0})
        else: opts.update({"min": -10000.0, "max": 10000.0})
        return ("FLOAT", opts)
    if isinstance(value, (list, dict)):
        return ("STRING", {"default": json.dumps(value, ensure_ascii=False, indent=2), "multiline": True, **common})

    default = "" if value is None else str(value)
    multiline = n in {
        "prompt", "text", "lyrics", "style", "negativeprompt", "negative_prompt",
        "instructions", "system_prompt", "description",
    } or len(default) > 120 or int(hint.get("maxLength") or 0) > 240
    options = {"default": default, "multiline": multiline, **common}
    if hint.get("maxLength"):
        options["dynamicPrompts"] = False
    return ("STRING", options)


def _payload_template(op: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    body = op.get("example_body") if isinstance(op.get("example_body"), dict) else {}
    market = str(op.get("endpoint") or "") == "/api/v1/jobs/createTask"
    if market and isinstance(body.get("input"), dict):
        return dict(body.get("input") or {}), True
    return dict(body), market


def _request_templates(op: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], bool]:
    body, market = _payload_template(op)
    query = op.get("example_query") if isinstance(op.get("example_query"), dict) else {}
    return dict(body), dict(query), market


def _all_parameter_names(op: dict[str, Any], body: dict[str, Any], query: dict[str, Any]) -> list[str]:
    names = list(body.keys()) + [x for x in query.keys() if x not in body]
    for name in (op.get("path_params") or []):
        if name not in names: names.append(str(name))
    for name in (op.get("parameter_hints") or {}).keys():
        if name not in names: names.append(str(name))
    return names


def _friendly_input_types(op: dict[str, Any], *, model: str = "") -> dict[str, dict[str, Any]]:
    title = str(op.get("title") or "")
    body, query, market = _request_templates(op)
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    hints = op.get("parameter_hints") or {}

    callback_names = {"callBackUrl", "callbackUrl", "callback_url"}
    has_callback = bool(callback_names.intersection(body) or callback_names.intersection(hints)) or market
    for field in callback_names:
        body.pop(field, None); query.pop(field, None)
    if market:
        body.pop("model", None)

    names = _all_parameter_names(op, body, query)
    for name in names:
        if name in callback_names or (name == "model" and model):
            continue
        hint = hints.get(name) or {}
        if name in body: value = body.get(name)
        elif name in query: value = query.get(name)
        else: value = _hint_default(hint)

        aliases = _media_aliases(name, value)
        if aliases:
            for alias, socket_type, force_required in aliases:
                (required if force_required else optional)[alias] = (socket_type,)
            continue
        if _is_image_field(name):
            widget = ("IMAGE",)
        elif _is_video_field(name):
            widget = ("VIDEO",)
        elif _is_audio_field(name):
            widget = ("AUDIO",)
        else:
            widget = _scalar_widget(name, value, op)

        is_path = name in (op.get("path_params") or [])
        is_required = bool(hint.get("required")) or is_path or name in {"prompt", "text"} or _required_media(title, name)
        (required if is_required else optional)[name] = widget

    # Skeleton docs remain recognizable/useful while the automatic deep sync runs.
    if not names:
        lower = title.lower()
        if any(word in lower for word in ("generate", "text to", "text-to", "video", "image", "speech", "voice", "lyrics")):
            required["prompt"] = (
                "STRING",
                {"default": "", "multiline": True, "tooltip": "Prompt sent to this KIE model."},
            )

    # Polished model nodes wait for their result. Advanced submit/status nodes remain
    # available separately for users who intentionally want asynchronous workflows.
    if str(op.get("method") or "POST").upper() != "GET":
        optional["timeout_seconds"] = ("INT", {"default": 1200, "min": 30, "max": 7200, "step": 30})
    if has_callback:
        optional["callback_url"] = (
            "STRING",
            {"default": "", "multiline": False, "tooltip": "Optional KIE callback URL. Leave empty for normal ComfyUI use."},
        )
    # A complete OpenAPI schema is the normal product surface. Preserve a raw
    # escape hatch only for documentation pages that still lack a request schema.
    if not hints:
        optional["expert_override_json"] = (
            "STRING",
            {
                "default": "{}",
                "multiline": True,
                "tooltip": "Expert-only payload overrides for APIs whose documentation has no request schema yet.",
            },
        )
    return {"required": required, "optional": optional}


# ------------------------------ payload building ----------------------------


def _parse_json_widget(value: str, name: str) -> Any:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain valid JSON: {exc}") from exc


def _media_value(client: KIEClient, field: str, value: Any) -> Any:
    if value is None:
        return None
    n = field.lower()
    if _is_image_field(field):
        urls = upload_image_batch(client, value, prefix=_slug(field).lower())
        # singular URL fields take the first image; plural/list fields take the whole batch.
        return urls if (field.endswith("s") or "urls" in n or n in {"input_urls", "image_input"}) else (urls[0] if urls else "")
    if _is_video_field(field):
        path = video_to_temp_file(value)
        url = client.upload_file(path, upload_path="comfyui/videos")
        return [url] if (field.endswith("s") or "urls" in n) else url
    if _is_audio_field(field):
        url = upload_audio(client, value, prefix=_slug(field).lower())
        return [url] if (field.endswith("s") or "urls" in n or "list" in n) else url
    return value


def _coerce_widget_value(name: str, example: Any, value: Any, client: KIEClient) -> Any:
    if _is_image_field(name) or _is_video_field(name) or _is_audio_field(name):
        return _media_value(client, name, value)
    if isinstance(example, (list, dict)) and isinstance(value, str):
        return _parse_json_widget(value, name)
    return value



def _collect_media_aliases(client: KIEClient, field: str, example: Any, kwargs: dict[str, Any]) -> list[str] | None:
    aliases = _media_aliases(field, example)
    if not aliases:
        return None
    urls: list[str] = []
    for alias, socket_type, _ in aliases:
        value = kwargs.get(alias)
        if value is None:
            continue
        if socket_type == "VIDEO":
            path = video_to_temp_file(value)
            urls.append(client.upload_file(path, upload_path="comfyui/videos"))
        else:
            urls.append(upload_audio(client, value, prefix=_slug(alias).lower()))
    return urls


def _build_payload(client: KIEClient, op: dict[str, Any], kwargs: dict[str, Any], *, model: str = "") -> dict[str, Any]:
    body, query, market = _request_templates(op)
    hints = op.get("parameter_hints") or {}
    out: dict[str, Any] = {}
    callback_names = {"callBackUrl", "callbackUrl", "callback_url"}
    path_names = set(str(x) for x in (op.get("path_params") or []))

    for name in _all_parameter_names(op, body, query):
        if name in callback_names or name in path_names:
            continue
        if name == "model" and model:
            continue
        example = body.get(name, query.get(name, _hint_default(hints.get(name) or {})))
        aliased_urls = _collect_media_aliases(client, name, example, kwargs)
        if aliased_urls is not None:
            if aliased_urls:
                out[name] = aliased_urls
            continue
        if name not in kwargs or kwargs[name] is None:
            continue
        value = kwargs[name]
        # Empty optional strings are omitted instead of overriding provider defaults.
        if value == "" and not bool((hints.get(name) or {}).get("required")):
            continue
        if _is_topaz_video_upscale(model) and _is_video_field(name):
            path = video_to_temp_file(value, canonical_h264_sdr=True)
            size_bytes = os.path.getsize(path)
            print(
                f"[KIE Next][Topaz] Prepared canonical H.264/SDR MP4 "
                f"({size_bytes / (1024 * 1024):.2f} MiB) before upload."
            )
            out[name] = client.upload_file(path, upload_path="comfyui/videos")
        else:
            out[name] = _coerce_widget_value(name, example, value, client)

    # Skeleton docs or a temporarily unresolved page still preserve the central prompt.
    if not out and str(kwargs.get("prompt") or "").strip():
        out["prompt"] = str(kwargs.get("prompt") or "")

    advanced = parse_object_json(
        str(kwargs.get("expert_override_json") or kwargs.get("advanced_json") or "{}"),
        "expert_override_json",
    )
    out.update(advanced)
    if not market and model:
        out["model"] = model
    return out


def _build_query(client: KIEClient, op: dict[str, Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    body, query_template, _ = _request_templates(op)
    hints = op.get("parameter_hints") or {}
    query_names = list(query_template.keys())
    # GET documentation sometimes describes query parameters in the parameter table
    # without repeating them in the cURL example.
    if str(op.get("method") or "").upper() == "GET":
        for name in hints:
            if name not in query_names and name not in (op.get("path_params") or []):
                query_names.append(name)
    out: dict[str, Any] = {}
    for name in query_names:
        if name not in kwargs or kwargs[name] is None or kwargs[name] == "":
            continue
        example = query_template.get(name, _hint_default(hints.get(name) or {}))
        out[name] = _coerce_widget_value(name, example, kwargs[name], client)
    advanced = parse_object_json(
        str(kwargs.get("expert_override_json") or "{}"), "expert_override_json"
    )
    # On GET nodes, expert overrides are query parameters.
    out.update(advanced)
    return out


def _substitute_path(endpoint: str, op: dict[str, Any], kwargs: dict[str, Any]) -> str:
    endpoint = str(endpoint)
    for name in (op.get("path_params") or []):
        value = str(kwargs.get(name) or "").strip()
        if not value:
            raise ValueError(f"{name} is required by this KIE endpoint path.")
        endpoint = endpoint.replace("{" + str(name) + "}", value)
        endpoint = endpoint.replace(":" + str(name), value)
    return endpoint


def _validate_special(model: str, payload: dict[str, Any]) -> None:
    if model in {"bytedance/seedance-2", "bytedance/seedance-2-fast", "bytedance/seedance-2-mini"}:
        has_frames = bool(payload.get("first_frame_url") or payload.get("last_frame_url"))
        has_refs = bool(payload.get("reference_image_urls") or payload.get("reference_video_urls") or payload.get("reference_audio_urls"))
        if has_frames and has_refs:
            raise ValueError(
                "Seedance 2.0: First/Last Frame mode and Multimodal Reference mode are mutually exclusive. "
                "Disconnect either the frame inputs or all reference inputs."
            )


def _extract_task_id(payload: Any) -> str:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("taskId", "task_id", "id"):
                if data.get(key):
                    return str(data[key])
        for key in ("taskId", "task_id"):
            if payload.get(key):
                return str(payload[key])
    return ""


def _all_urls(payload: Any) -> list[str]:
    return KIEClient.extract_result_urls({"resultJson": payload})


def _credits_from(payload: Any) -> float:
    found = 0.0
    def walk(v: Any):
        nonlocal found
        if isinstance(v, dict):
            for k, x in v.items():
                if k in {"credits_consumed", "creditsConsumed"} and isinstance(x, (int, float)):
                    found = float(x)
                else:
                    walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
    walk(payload)
    return found


def _direct_status_endpoint(op: dict[str, Any]) -> tuple[str, str] | None:
    family = str(op.get("family") or "").lower()
    if "suno" in family:
        return "/api/v1/generate/record-info", "suno"
    if "veo" in family:
        return "/api/v1/veo/record-info", "flag"
    if "runway" in family:
        return "/api/v1/runway/record-detail", "state"
    if "4o image" in family:
        return "/api/v1/gpt4o-image/record-info", "flag"
    if "flux kontext" in family:
        return "/api/v1/flux/kontext/record-info", "flag"
    return None


def _wait_direct(client: KIEClient, op: dict[str, Any], task_id: str, timeout: int) -> Any:
    poll = _direct_status_endpoint(op)
    if not poll:
        return None
    endpoint, mode = poll
    deadline = time.monotonic() + float(timeout)
    interval = 2.5
    last: Any = None
    while time.monotonic() < deadline:
        last = client.raw_api_request("GET", endpoint, query={"taskId": task_id})
        data = last.get("data") if isinstance(last, dict) else None
        if not isinstance(data, dict):
            time.sleep(interval); continue
        if mode == "suno":
            status = str(data.get("status") or "").upper()
            if status == "SUCCESS": return last
            if status in {"CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR", "FAILED"}:
                raise KIEAPIError(f"KIE Suno task failed: {data.get('errorMessage') or status}", payload=last)
        elif mode == "state":
            state = str(data.get("state") or "").lower()
            if state == "success": return last
            if state in {"fail", "failed"}:
                raise KIEAPIError(f"KIE Runway task failed: {data.get('failMsg') or state}", payload=last)
        else:
            flag = data.get("successFlag")
            if flag == 1: return last
            if flag in {2, 3}:
                raise KIEAPIError(f"KIE task failed: {data.get('errorMessage') or data.get('failMsg') or flag}", payload=last)
        time.sleep(interval)
        interval = min(interval * 1.4, 12.0)
    raise KIEAPIError(f"Timed out waiting for KIE direct task {task_id}", payload=last)


# ------------------------------- output adapters ----------------------------


def _output_signature(kind: str):
    if kind == "image":
        return ("IMAGE", "STRING", "STRING", "STRING", "STRING", "FLOAT"), ("image", "url", "all_urls_json", "task_id", "raw_json", "credits_consumed")
    if kind == "video":
        return ("VIDEO", "STRING", "STRING", "STRING", "STRING", "FLOAT"), ("video", "url", "all_urls_json", "task_id", "raw_json", "credits_consumed")
    if kind == "audio":
        return ("AUDIO", "STRING", "STRING", "STRING", "STRING", "FLOAT"), ("audio", "url", "all_urls_json", "task_id", "raw_json", "credits_consumed")
    if kind == "text":
        return ("STRING", "STRING", "STRING", "FLOAT"), ("text", "task_id", "raw_json", "credits_consumed")
    return ("STRING", "STRING", "STRING"), ("raw_json", "first_url", "task_id")


def _preferred_urls(urls: list[str], kind: str) -> list[str]:
    suffixes = {
        "image": (".png", ".jpg", ".jpeg", ".webp", ".gif"),
        "video": (".mp4", ".mov", ".webm", ".mkv"),
        "audio": (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"),
    }.get(kind, ())
    preferred = [u for u in urls if u.lower().split("?", 1)[0].endswith(suffixes)] if suffixes else []
    return preferred or urls


def _result_for_kind(client: KIEClient, kind: str, payload: Any, task_id: str, credits: float = 0.0):
    all_urls = _all_urls(payload)
    urls = _preferred_urls(all_urls, kind)
    url = urls[0] if urls else ""
    all_urls_json = json.dumps(all_urls, ensure_ascii=False, indent=2)
    if kind == "image":
        if not url: raise KIEAPIError("KIE task completed but returned no image URL.", payload=payload)
        return (download_image_tensor(client, url), url, all_urls_json, task_id, pretty_json(payload), credits)
    if kind == "video":
        if not url: raise KIEAPIError("KIE task completed but returned no video URL.", payload=payload)
        return (download_video_object(client, url), url, all_urls_json, task_id, pretty_json(payload), credits)
    if kind == "audio":
        if not url: raise KIEAPIError("KIE task completed but returned no audio URL.", payload=payload)
        return (download_audio_object(client, url), url, all_urls_json, task_id, pretty_json(payload), credits)
    if kind == "text":
        text = _extract_text(payload)
        return (text, task_id, pretty_json(payload), credits or _credits_from(payload))
    return (pretty_json(payload), url, task_id)


def _extract_text(payload: Any) -> str:
    chunks: list[str] = []
    def walk(v: Any):
        if isinstance(v, dict):
            # Prefer explicit output text fields.
            for k in ("text", "output_text", "content", "lyrics"):
                x = v.get(k)
                if isinstance(x, str) and x.strip(): chunks.append(x)
            for x in v.values(): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
    walk(payload)
    # Stable de-duplication while preserving order.
    return "\n".join(dict.fromkeys(x.strip() for x in chunks if x.strip()))


# ------------------------------- LLM adapter ---------------------------------


def _llm_input_types(op: dict[str, Any]) -> dict[str, dict[str, Any]]:
    family = str(op.get("family") or "").lower()
    endpoint = str(op.get("endpoint") or "").lower()
    summary = str(op.get("summary") or "").lower()
    is_claude = "claude" in family or endpoint.startswith("/claude/")
    is_openai_reasoning = any(x in family for x in ("gpt", "codex", "grok")) or endpoint.startswith("/codex/")
    mentions_images = "image" in summary or any("image" in str(k).lower() for k in (op.get("parameter_hints") or {}))

    required = {
        "prompt": ("STRING", {"default": "", "multiline": True, "tooltip": "User prompt / message."}),
    }
    optional: dict[str, Any] = {
        "system_prompt": ("STRING", {"default": "", "multiline": True}),
        "stream": ("BOOLEAN", {"default": False}),
        "tools_json": ("STRING", {"default": "[]", "multiline": True, "tooltip": "Optional function/tool definitions supported by this model endpoint."}),
        "history_json": ("STRING", {"default": "[]", "multiline": True, "tooltip": "Optional prior message/input array as JSON."}),
    }
    if is_openai_reasoning:
        optional["images"] = ("IMAGE",)
        optional["reasoning_effort"] = (_REASONING, {"default": "high"})
        optional["web_search"] = ("BOOLEAN", {"default": False, "tooltip": "Use KIE's web-search tool where this endpoint supports it."})
    elif mentions_images and not is_claude:
        optional["images"] = ("IMAGE",)
    if is_claude:
        optional["max_tokens"] = ("INT", {"default": 4096, "min": 1, "max": 131072, "step": 1})
        optional["thinking"] = ("BOOLEAN", {"default": False})
    elif any(str(k).lower() in {"max_tokens", "max_output_tokens"} for k in (op.get("parameter_hints") or {})):
        optional["max_tokens"] = ("INT", {"default": 4096, "min": 1, "max": 131072, "step": 1})
    optional["expert_override_json"] = (
        "STRING",
        {"default": "{}", "multiline": True, "tooltip": "Expert-only request overrides. Normal use does not require this."},
    )
    return {"required": required, "optional": optional}


def _model_from_op(op: dict[str, Any], fallback: str = "") -> str:
    models = [str(x) for x in (op.get("models") or []) if str(x).strip()]
    if fallback: return fallback
    if len(models) == 1: return models[0]
    body = op.get("example_body") or {}
    if isinstance(body, dict) and isinstance(body.get("model"), str): return body["model"]
    return str(op.get("default_model") or "")


def _execute_llm(op: dict[str, Any], model: str, kwargs: dict[str, Any]):
    client = make_client(None)
    endpoint = str(op.get("endpoint") or "")
    if not endpoint:
        resolved = resolve_operation(str(op.get("label") or "")) or op
        endpoint = str(resolved.get("endpoint") or "")
        op = resolved
    if not endpoint:
        raise KIEAPIError("This model's endpoint has not been resolved yet. Refresh KIE Next's live catalog once.")

    prompt = str(kwargs.get("prompt") or "")
    system_prompt = str(kwargs.get("system_prompt") or "").strip()
    tools = _parse_json_widget(str(kwargs.get("tools_json") or "[]"), "tools_json")
    history = _parse_json_widget(str(kwargs.get("history_json") or "[]"), "history_json")
    advanced = parse_object_json(str(kwargs.get("expert_override_json") or kwargs.get("advanced_json") or "{}"), "expert_override_json")
    image_urls = upload_image_batch(client, kwargs.get("images"), prefix="kie_llm") if kwargs.get("images") is not None else []
    family = str(op.get("family") or "").lower()

    if "claude" in family or endpoint.startswith("/claude/"):
        messages = list(history) if isinstance(history, list) else []
        # Keep simple text prompt first-class. Multimodal Claude payloads can still be supplied through history_json/expert_override_json.
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": bool(kwargs.get("stream", False)),
            "max_tokens": int(kwargs.get("max_tokens", 4096)),
        }
        if system_prompt: body["system"] = system_prompt
        if tools: body["tools"] = tools
        if "thinking" in kwargs: body["thinkingFlag"] = bool(kwargs.get("thinking"))
    elif endpoint.startswith("/codex/") or "gpt" in family or "codex" in family:
        input_items = list(history) if isinstance(history, list) else []
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        content.extend({"type": "input_image", "image_url": url} for url in image_urls)
        input_items.append({"role": "user", "content": content})
        body = {"model": model, "input": input_items, "reasoning": {"effort": str(kwargs.get("reasoning_effort") or "high")}}
        if system_prompt:
            body["instructions"] = system_prompt
        if bool(kwargs.get("web_search")):
            body["tools"] = [{"type": "web_search"}]
        elif tools:
            body["tools"] = tools
        if kwargs.get("stream"):
            body["stream"] = True
    else:
        messages = list(history) if isinstance(history, list) else []
        if system_prompt: messages.insert(0, {"role": "system", "content": system_prompt})
        user_content: Any = prompt
        if image_urls:
            user_content = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {"url": url}} for url in image_urls
            ]
        messages.append({"role": "user", "content": user_content})
        body = {"model": model, "messages": messages, "stream": bool(kwargs.get("stream", False))}
        if tools: body["tools"] = tools
        if "max_tokens" in kwargs: body["max_tokens"] = int(kwargs.get("max_tokens") or 4096)

    body.update(advanced)
    payload = client.raw_api_request("POST", endpoint, body=body)
    return (_extract_text(payload), pretty_json(payload), _credits_from(payload), pretty_json(payload.get("usage") if isinstance(payload, dict) else {}))


# ----------------------------- class factories -------------------------------


def _is_topaz_video_upscale(model: str) -> bool:
    return str(model or "").strip().lower() == "topaz/video-upscale"


def _normalize_topaz_video_payload(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Topaz's stricter Market payload before a paid task is submitted."""
    if not _is_topaz_video_upscale(model):
        return payload

    video_url = payload.get("video_url")
    if not isinstance(video_url, str) or not video_url.strip():
        raise KIEAPIError(
            "Topaz Video Upscale requires a valid video input. Connect a VIDEO to video_url before running the node."
        )

    raw_factor = payload.get("upscale_factor", "2")
    factor = str(raw_factor).strip().lower()
    if factor.endswith("x"):
        factor = factor[:-1].strip()
    if factor.endswith(".0"):
        factor = factor[:-2]
    if factor not in {"1", "2", "4"}:
        raise KIEAPIError(
            f"Topaz Video Upscale upscale_factor must be 1, 2, or 4 (received {raw_factor!r})."
        )

    normalized = dict(payload)
    normalized["video_url"] = video_url.strip()
    # KIE's current Topaz API documents this value as a string.
    normalized["upscale_factor"] = factor
    return normalized


def _retryable_topaz_internal_error(exc: KIEAPIError) -> bool:
    message = str(exc).lower()
    return (
        "internal error" in message
        or "internal server error" in message
        or "please try again later" in message
    )


def _topaz_failure_message(task_ids: list[str], exc: KIEAPIError) -> str:
    ids = ", ".join(task_ids) if task_ids else "unknown"
    return (
        "Topaz Video Upscale was accepted by KIE but the remote Topaz provider failed during processing. "
        "KIE Next retried the provider once and the retry also failed. "
        f"Task ID(s): {ids}. Provider message: {exc}. "
        "This is a remote KIE/Topaz processing failure, not a local CUDA/VRAM error. "
        "Try a short H.264 MP4 at 2x to isolate source compatibility; if that succeeds, transcode the original "
        "video to H.264/MP4 before upscaling."
    )


def _market_execute(op: dict[str, Any], model: str, kind: str, kwargs: dict[str, Any], payload_model: str | None = None):
    client = make_client(None)
    payload = _build_payload(client, op, kwargs, model=model)
    payload = _normalize_topaz_video_payload(model, payload)
    _validate_special(model, payload)
    callback = str(kwargs.get("callback_url") or "").strip()
    timeout_seconds = int(kwargs.get("timeout_seconds", 1200))

    # Topaz occasionally returns a terminal provider-side "internal error" only
    # seconds after accepting a task. Retry exactly once for that narrow failure
    # signature. Other models and all validation/auth/billing failures keep the
    # previous single-submit behavior.
    max_attempts = 2 if _is_topaz_video_upscale(model) else 1
    task_ids: list[str] = []
    result = None
    last_error: KIEAPIError | None = None

    for attempt in range(max_attempts):
        task_id = client.create_task(model, payload, callback_url=callback)
        task_ids.append(task_id)
        try:
            result = client.wait_for_task(task_id, timeout_seconds=timeout_seconds)
            break
        except KIEAPIError as exc:
            last_error = exc
            if attempt + 1 < max_attempts and _retryable_topaz_internal_error(exc):
                time.sleep(2.0)
                continue
            if _is_topaz_video_upscale(model) and _retryable_topaz_internal_error(exc):
                raise KIEAPIError(_topaz_failure_message(task_ids, exc), payload=getattr(exc, "payload", None)) from exc
            raise

    if result is None:
        if last_error is not None:
            raise last_error
        raise KIEAPIError("KIE task ended without a result.")

    task_id = task_ids[-1]
    payload_out = result.raw
    if kind in {"image", "video", "audio", "text"}:
        return _result_for_kind(client, kind, payload_out, task_id, result.credits_consumed)
    return (pretty_json(payload_out), result.urls[0] if result.urls else "", task_id)


def _direct_execute(op: dict[str, Any], model: str, kind: str, kwargs: dict[str, Any]):
    client = make_client(None)
    resolved = resolve_operation(str(op.get("label") or "")) or op
    method = str(resolved.get("method") or "POST").upper()
    endpoint = str(resolved.get("endpoint") or "")
    if not endpoint:
        raise KIEAPIError("This KIE API page has not been resolved yet. KIE Next will retry from the official docs; you can also run Refresh Live Catalog.")
    endpoint = _substitute_path(endpoint, resolved, kwargs)

    if method == "GET":
        query = _build_query(client, resolved, kwargs)
        payload = client.raw_api_request("GET", endpoint, query=query)
        # Status/detail/download operations return metadata, not an unexpected
        # media download. Generation nodes are the ones that return IMAGE/VIDEO/AUDIO.
        return _result_for_kind(client, kind if kind == "text" else "utility", payload, _extract_task_id(payload), _credits_from(payload))

    body = _build_payload(client, resolved, kwargs, model=model)
    callback = str(kwargs.get("callback_url") or "").strip()
    if callback:
        body.setdefault("callBackUrl", callback)
    payload = client.raw_api_request(method, endpoint, body=body)
    task_id = _extract_task_id(payload)
    if task_id:
        completed = _wait_direct(client, resolved, task_id, int(kwargs.get("timeout_seconds", 1200)))
        if completed is not None:
            payload = completed
    if kind in {"image", "video", "audio", "text"} and _all_urls(payload):
        return _result_for_kind(client, kind, payload, task_id, _credits_from(payload))
    if kind == "text":
        return _result_for_kind(client, "text", payload, task_id, _credits_from(payload))
    return (pretty_json(payload), (_all_urls(payload) or [""])[0], task_id)


def make_model_node(op: dict[str, Any], model: str = ""):
    kind = kind_for(op)
    title = display_name_for(op, model)
    category = category_for(op)
    resolved_model = model or _model_from_op(op)
    is_llm = kind == "llm"
    market = str(op.get("endpoint") or "") == "/api/v1/jobs/createTask"
    return_types, return_names = (("STRING", "STRING", "FLOAT", "STRING"), ("text", "raw_json", "credits_consumed", "usage_json")) if is_llm else _output_signature(kind)

    class GeneratedKIEModelNode:
        OP = op
        MODEL = resolved_model
        @classmethod
        def INPUT_TYPES(cls):
            # Re-read the operation from live catalog so deep-sync improvements can
            # enrich an already-registered node after a UI reload.
            current = resolve_operation(str(cls.OP.get("label") or "")) or cls.OP
            return _llm_input_types(current) if is_llm else _friendly_input_types(current, model=cls.MODEL)

        RETURN_TYPES = return_types
        RETURN_NAMES = return_names
        FUNCTION = "execute"
        CATEGORY = category
        DESCRIPTION = str(op.get("summary") or f"KIE.ai • {title}")[:700]

        def execute(self, **kwargs):
            current = resolve_operation(str(self.OP.get("label") or "")) or self.OP
            fixed_model = self.MODEL or _model_from_op(current)
            if is_llm:
                return _execute_llm(current, fixed_model, kwargs)
            current_market = str(current.get("endpoint") or "") == "/api/v1/jobs/createTask" or market
            if current_market:
                if not fixed_model:
                    raise KIEAPIError("KIE model ID has not been resolved yet. Refresh the live catalog once.")
                return _market_execute(current, fixed_model, kind, kwargs)
            return _direct_execute(current, fixed_model, kind, kwargs)

    GeneratedKIEModelNode.__name__ = f"Generated_{_slug(title)}_{hashlib.sha1((resolved_model or title).encode()).hexdigest()[:6]}"
    return GeneratedKIEModelNode


def _pretty_model_variant(model: str) -> str:
    text = str(model or "").strip()
    if not text:
        return ""
    # Keep official identifiers recognizable while making common version labels
    # pleasant in ComfyUI's add-node menu.
    if re.fullmatch(r"V\d+(?:_\d+)*(?:PLUS|ALL)?", text, re.I):
        text = text.replace("_", ".")
    elif text.lower().startswith("veo"):
        text = re.sub(r"^veo", "Veo ", text, flags=re.I).replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _model_variants_for(op: dict[str, Any]) -> list[str]:
    """Return fixed model IDs/versions that deserve individual nodes.

    KIE Market pages usually expose explicit model IDs. Some direct APIs (notably
    Suno/Veo and a few chat-style endpoints) expose a `model` enum instead. Those
    should still become one node per model/version rather than a generic node with
    a model dropdown.
    """
    variants = [str(m).strip() for m in (op.get("models") or []) if str(m).strip()]
    hint = (op.get("parameter_hints") or {}).get("model") or {}
    for value in _enum_from_hint(hint):
        value = str(value).strip()
        if value and value not in variants:
            variants.append(value)

    body = op.get("example_body") if isinstance(op.get("example_body"), dict) else {}
    body_model = str(body.get("model") or "").strip()
    if body_model and body_model not in variants:
        variants.append(body_model)
    return variants


def generated_node_mappings() -> tuple[dict[str, type], dict[str, str]]:
    catalog = load_catalog()
    classes: dict[str, type] = {}
    names: dict[str, str] = {}
    for op in catalog.get("operations") or []:
        # One official documentation page may publish multiple model IDs/versions.
        # Split every explicit model variant into its own ComfyUI node, regardless
        # of whether KIE transports it through Market createTask or a direct API.
        variants = _model_variants_for(op)
        if variants:
            for model in variants:
                node_id = node_id_for(op, model)
                classes[node_id] = make_model_node(op, model)
                base = display_name_for(op, model)
                names[node_id] = base if len(variants) == 1 else f"{base} · {_pretty_model_variant(model)}"
        else:
            # Operations that are not model-versioned (upload, task detail, stems,
            # lyrics utilities, etc.) are still represented by one dedicated node.
            node_id = node_id_for(op)
            classes[node_id] = make_model_node(op)
            names[node_id] = display_name_for(op)
    return classes, names

