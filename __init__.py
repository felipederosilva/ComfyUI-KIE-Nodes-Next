from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__version__ = "0.3.5"

WEB_DIRECTORY = "./js"

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

