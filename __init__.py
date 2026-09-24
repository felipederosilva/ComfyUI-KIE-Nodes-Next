from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__version__ = "0.4.16"

WEB_DIRECTORY = "./js"

try:
    from .kie.media_compat import install as _install_media_compat
    _install_media_compat()
except Exception as exc:
    # Media compatibility is optional and must never prevent node loading.
    print(f"[KIE Next] Nested input-media compatibility disabled: {exc}")

# Refuse to run a mixed install (for example, a new __init__.py with an old
# nodes/generated.py). This is safer than reporting a new version while silently
# executing stale paid-generation code.
try:
    from .nodes import generated as _generated
    _generated_build = getattr(_generated, "KIE_GENERATED_BUILD", None)
    if _generated_build != __version__:
        raise RuntimeError(
            "KIE Next install integrity check failed: package version "
            f"{__version__}, generated node build {_generated_build or 'legacy/unknown'}. "
            "Your installation contains files from different releases. "
            "Delete the entire ComfyUI-KIE-Nodes-Next folder and reinstall from the repository."
        )
except Exception:
    raise


from pathlib import Path as _Path
_PLUGIN_ROOT = _Path(__file__).resolve().parent
print(f"[KIE Next] Loaded v{__version__} from {_PLUGIN_ROOT}")

try:
    from .kie.server import register_routes
    register_routes()
except Exception as exc:
    # The package is also imported by offline tests where ComfyUI's PromptServer
    # does not exist. Node registration should still succeed in that environment.
    print(f"[KIE Next] HTTP settings routes not registered: {exc}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY", "__version__"]

