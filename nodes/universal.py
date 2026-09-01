from __future__ import annotations

import json

from ..kie.catalog import catalog_summary, model_options, operation_options, resolve_operation, sync_catalog
from ..kie.client import KIEClient, pretty_json
from ..kie.helpers import apply_path_params, make_client, parse_object_json, replace_placeholders
from ..kie.media import upload_audio, upload_image_batch, video_to_temp_file


def _media_replacements(client, images=None, video=None, audio=None) -> dict[str, object]:
    replacements: dict[str, object] = {
        "$image_urls": [],
        "$image_url": "",
        "$video_url": "",
        "$audio_url": "",
    }
    if images is not None:
        urls = upload_image_batch(client, images, prefix="kie_universal")
        replacements["$image_urls"] = urls
        replacements["$image_url"] = urls[0] if urls else ""
    if video is not None:
        path = video_to_temp_file(video)
        replacements["$video_url"] = client.upload_file(path, upload_path="comfyui/videos")
    if audio is not None:
        replacements["$audio_url"] = upload_audio(client, audio, prefix="kie_universal")
    return replacements



class KIEUniversalTaskNode:
    @classmethod
    def INPUT_TYPES(cls):
        options = model_options()
        return {
            "required": {
                "model": (options, {"default": options[0]}),
                "input_json": ("STRING", {"default": '{\n  "prompt": ""\n}', "multiline": True}),
                "wait_for_completion": ("BOOLEAN", {"default": True}),
                "timeout_seconds": ("INT", {"default": 900, "min": 30, "max": 7200, "step": 30}),
            },
            "optional": {
                "custom_model": ("STRING", {"default": "", "multiline": False}),
                "images": ("IMAGE",),
                "video": ("VIDEO",),
                "audio": ("AUDIO",),
                "callback_url": ("STRING", {"default": "", "multiline": False}),
                "config": ("KIE_CONFIG",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "FLOAT")
    RETURN_NAMES = ("task_id", "state", "result_urls_json", "raw_json", "credits_consumed")
    FUNCTION = "run"
    CATEGORY = "KIE Next/Advanced/API Tools"
    DESCRIPTION = (
        "Universal wrapper for every KIE Market createTask model discovered from KIE's live documentation. "
        "Use $image_urls, $image_url, $video_url or $audio_url as exact JSON values to inject local Comfy media."
    )

    def run(
        self,
        model,
        input_json,
        wait_for_completion,
        timeout_seconds,
        custom_model="",
        images=None,
        video=None,
        audio=None,
        callback_url="",
        config=None,
    ):
        client = make_client(config)
        payload = parse_object_json(input_json, "input_json")
        payload = replace_placeholders(payload, _media_replacements(client, images, video, audio))
        chosen_model = (custom_model or model).strip()
        task_id = client.create_task(chosen_model, payload, callback_url=callback_url)
        if not wait_for_completion:
            return (task_id, "submitted", "[]", "{}", 0.0)
        result = client.wait_for_task(task_id, timeout_seconds=timeout_seconds)
        return (
            task_id,
            result.state,
            json.dumps(result.urls, ensure_ascii=False),
            pretty_json(result.raw),
            result.credits_consumed,
        )


class KIEAnyAPIRequestNode:
    @classmethod
    def INPUT_TYPES(cls):
        options = operation_options()
        return {
            "required": {
                "operation": (options, {"default": options[0]}),
                "query_json": ("STRING", {"default": "{}", "multiline": True}),
                "body_json": ("STRING", {"default": "{}", "multiline": True}),
            },
            "optional": {
                "custom_method": (["", "GET", "POST", "PUT", "PATCH", "DELETE"], {"default": ""}),
                "custom_endpoint": ("STRING", {"default": "", "multiline": False}),
                "path_params_json": ("STRING", {"default": "{}", "multiline": True}),
                "images": ("IMAGE",),
                "video": ("VIDEO",),
                "audio": ("AUDIO",),
                "config": ("KIE_CONFIG",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("raw_json", "first_url")
    FUNCTION = "request"
    CATEGORY = "KIE Next/Advanced/API Tools"
    DESCRIPTION = (
        "Calls every REST operation discovered from KIE's live API docs: Suno, Veo, Runway, chat, file/common, "
        "legacy/direct image/video APIs and more. Use local-media placeholders in body_json. "
        "Authenticated custom endpoints are security-locked to api.kie.ai."
    )

    def request(
        self,
        operation,
        query_json,
        body_json,
        custom_method="",
        custom_endpoint="",
        path_params_json="{}",
        images=None,
        video=None,
        audio=None,
        config=None,
    ):
        op = resolve_operation(operation) or {}
        method = (custom_method or op.get("method") or "GET").upper()
        endpoint = (custom_endpoint or op.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError("No endpoint is available for this operation yet. Refresh the KIE catalog or enter custom_endpoint.")
        path_params = parse_object_json(path_params_json, "path_params_json")
        endpoint = apply_path_params(endpoint, path_params)
        query = parse_object_json(query_json, "query_json")
        body = parse_object_json(body_json, "body_json")
        default_model = str(op.get("default_model") or "").strip()
        if default_model and "model" not in body:
            body["model"] = default_model

        client = make_client(config)
        replacements = _media_replacements(client, images, video, audio)
        query = replace_placeholders(query, replacements)
        body = replace_placeholders(body, replacements)
        payload = client.raw_api_request(method, endpoint, query=query, body=body)
        urls = KIEClient.extract_result_urls({"resultJson": payload}) if isinstance(payload, (dict, list, str)) else []
        return (pretty_json(payload), urls[0] if urls else "")


class KIEAPIDescribeNode:
    @classmethod
    def INPUT_TYPES(cls):
        options = operation_options()
        return {"required": {"operation": (options, {"default": options[0]})}}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("method", "endpoint", "docs_url", "example_body_json", "default_model")
    FUNCTION = "describe"
    CATEGORY = "KIE Next/Advanced/API Tools"
    DESCRIPTION = "Shows the live-catalog metadata and example body for a discovered KIE API operation."

    def describe(self, operation):
        op = resolve_operation(operation) or {}
        example = op.get("example_body") if isinstance(op.get("example_body"), dict) else {}
        return (
            str(op.get("method") or ""),
            str(op.get("endpoint") or ""),
            str(op.get("docs_url") or ""),
            pretty_json(example),
            str(op.get("default_model") or ""),
        )


class KIEWaitTaskNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "task_id": ("STRING", {"default": "", "multiline": False}),
                "timeout_seconds": ("INT", {"default": 900, "min": 30, "max": 7200, "step": 30}),
            },
            "optional": {"config": ("KIE_CONFIG",)},
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "FLOAT")
    RETURN_NAMES = ("state", "result_urls_json", "raw_json", "credits_consumed")
    FUNCTION = "wait"
    CATEGORY = "KIE Next/Utility/Tasks"

    def wait(self, task_id, timeout_seconds, config=None):
        result = make_client(config).wait_for_task(task_id.strip(), timeout_seconds=timeout_seconds)
        return (
            result.state,
            json.dumps(result.urls, ensure_ascii=False),
            pretty_json(result.raw),
            result.credits_consumed,
        )


class KIETaskStatusNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"task_id": ("STRING", {"default": ""})},
            "optional": {"config": ("KIE_CONFIG",)},
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("state", "progress", "raw_json")
    FUNCTION = "status"
    CATEGORY = "KIE Next/Utility/Tasks"

    def status(self, task_id, config=None):
        data = make_client(config).get_task(task_id.strip())
        return (str(data.get("state") or ""), int(data.get("progress") or 0), pretty_json(data))


class KIECatalogSyncNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"refresh": ("BOOLEAN", {"default": True})}}

    RETURN_TYPES = ("STRING", "INT", "INT")
    RETURN_NAMES = ("status_json", "models", "api_operations")
    FUNCTION = "sync"
    CATEGORY = "KIE Next/Setup"
    OUTPUT_NODE = True

    def sync(self, refresh):
        result = sync_catalog() if refresh else {"ok": True, **catalog_summary()}
        return (pretty_json(result), int(result.get("models") or 0), int(result.get("operations") or 0))

