from __future__ import annotations

import asyncio
from pathlib import Path

from .catalog import catalog_summary, sync_catalog
from .client import KIEAPIError, KIEClient, KIEConfig
from .settings import (
    clear_api_key,
    get_api_key,
    public_status,
    save_api_key,
    save_validation_state,
)


def _plugin_diagnostics() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    version = "unknown"
    try:
        init_text = (root / "__init__.py").read_text(encoding="utf-8", errors="ignore")
        import re
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)', init_text)
        if match:
            version = match.group(1)
    except Exception:
        pass
    return {"plugin_version": version, "plugin_path": str(root)}


def _refresh_generated_nodes() -> None:
    try:
        from ..nodes import refresh_generated_nodes
        refresh_generated_nodes()
    except Exception as exc:
        print(f"[KIE Next] Generated node refresh warning: {exc}")


def _validate_key(key: str) -> float:
    config = KIEConfig.from_values(api_key=key, use_env_key=False)
    client = KIEClient(config)
    return client.get_credits()


def register_routes() -> bool:
    try:
        from aiohttp import web  # type: ignore
        from server import PromptServer  # type: ignore
    except Exception:
        return False

    routes = PromptServer.instance.routes

    @routes.get("/kie-next/settings")
    async def kie_settings_status(request):
        return web.json_response({"ok": True, **public_status(), "catalog": catalog_summary(), **_plugin_diagnostics()})

    @routes.post("/kie-next/settings/api-key")
    async def kie_settings_key(request):
        payload = await request.json()
        key = str((payload or {}).get("api_key") or "").strip()
        if not key:
            return web.json_response({"ok": False, "error": "API key is empty."}, status=400)
        loop = asyncio.get_running_loop()
        try:
            credits = await loop.run_in_executor(None, lambda: _validate_key(key))
        except KIEAPIError as exc:
            # Never replace a previously working key with an invalid one.
            status = 401 if exc.status in {401, 403} else 502
            return web.json_response(
                {
                    "ok": False,
                    "valid": False,
                    "error": str(exc),
                    **public_status(),
                    "attempt_validation_state": "invalid" if status == 401 else "unreachable",
                },
                status=status,
            )
        except Exception as exc:
            return web.json_response({"ok": False, "valid": False, "error": str(exc)}, status=502)

        save_api_key(key, credits=credits, validation_state="connected")
        return web.json_response({"ok": True, "valid": True, "credits": credits, **public_status()})

    @routes.post("/kie-next/settings/test")
    async def kie_settings_test(request):
        key = get_api_key()
        if not key:
            return web.json_response({"ok": False, "valid": False, "error": "No API key is saved."}, status=400)
        loop = asyncio.get_running_loop()
        try:
            credits = await loop.run_in_executor(None, lambda: _validate_key(key))
            save_validation_state("connected", credits=credits)
            return web.json_response({"ok": True, "valid": True, "credits": credits, **public_status()})
        except KIEAPIError as exc:
            state = "invalid" if exc.status in {401, 403} else "unreachable"
            save_validation_state(state, message=str(exc))
            return web.json_response({"ok": False, "valid": False, "error": str(exc), **public_status()}, status=401 if state == "invalid" else 502)

    @routes.delete("/kie-next/settings/api-key")
    async def kie_settings_clear(request):
        clear_api_key()
        return web.json_response({"ok": True, **public_status()})

    @routes.post("/kie-next/catalog/index")
    async def kie_catalog_index(request):
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: sync_catalog(index_only=True))
        _refresh_generated_nodes()
        return web.json_response(result)

    @routes.post("/kie-next/catalog/sync")
    async def kie_catalog_sync(request):
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, sync_catalog)
        _refresh_generated_nodes()
        return web.json_response(result)

    @routes.get("/kie-next/catalog/status")
    async def kie_catalog_status(request):
        return web.json_response({"ok": True, **catalog_summary()})

    return True

