from __future__ import annotations

from ..kie.client import DEFAULT_API_BASE, DEFAULT_UPLOAD_BASE, KIEConfig
from ..kie.helpers import make_client
from ..kie.settings import public_status


class KIEConfigNode:
    """Legacy/advanced config node. Normal v0.3 workflows do not need it."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "use_saved_key": ("BOOLEAN", {"default": True}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "api_base": ("STRING", {"default": DEFAULT_API_BASE, "multiline": False}),
                "upload_base": ("STRING", {"default": DEFAULT_UPLOAD_BASE, "multiline": False}),
            },
            "optional": {
                "request_timeout": ("FLOAT", {"default": 90.0, "min": 10.0, "max": 600.0, "step": 5.0}),
                "max_retries": ("INT", {"default": 4, "min": 0, "max": 10}),
            },
        }

    RETURN_TYPES = ("KIE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "build"
    CATEGORY = "KIE Next/Advanced/Connection"
    DESCRIPTION = "Optional advanced override. Normal KIE Next nodes automatically use the API key saved once in ComfyUI Settings."

    def build(self, use_saved_key, api_key, api_base, upload_base, request_timeout=90.0, max_retries=4):
        return (
            KIEConfig.from_values(
                api_key=api_key,
                use_env_key=use_saved_key,
                api_base=api_base,
                upload_base=upload_base,
                request_timeout=request_timeout,
                max_retries=max_retries,
            ),
        )


class KIECreditsNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {"config": ("KIE_CONFIG",)}}

    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("credits",)
    FUNCTION = "credits"
    CATEGORY = "KIE Next/Utility"

    def credits(self, config=None):
        return (make_client(config).get_credits(),)


class KIEConnectionStatusNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("configured", "source", "status_json")
    FUNCTION = "status"
    CATEGORY = "KIE Next/Setup"

    def status(self):
        import json
        status = public_status()
        return (bool(status["configured"]), str(status["source"]), json.dumps(status, ensure_ascii=False, indent=2))

