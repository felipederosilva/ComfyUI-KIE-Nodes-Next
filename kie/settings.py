from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_SETTINGS_FILENAME = "kie_nodes_next.json"


def _user_config_dir() -> Path:
    override = os.getenv("KIE_NODES_NEXT_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    try:
        import folder_paths  # type: ignore
        getter = getattr(folder_paths, "get_user_directory", None)
        if callable(getter):
            return Path(getter()) / "KIE-Nodes-Next"
    except Exception:
        pass

    if os.name == "nt":
        root = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
        return root / "ComfyUI" / "KIE-Nodes-Next"
    return Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / "comfyui" / "kie-nodes-next"


def settings_path() -> Path:
    path = _user_config_dir() / _SETTINGS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict[str, Any]:
    path = settings_path()
    with _LOCK:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}


def save_settings(values: dict[str, Any]) -> None:
    path = settings_path()
    with _LOCK:
        current = load_settings()
        current.update(values)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def save_api_key(api_key: str, *, credits: float | None = None, validation_state: str = "saved") -> None:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API key cannot be empty.")
    payload: dict[str, Any] = {
        "api_key": key,
        "key_saved_at": int(time.time()),
        "key_validation_state": validation_state,
        "key_validated_at": int(time.time()),
        "key_validation_message": "",
    }
    if credits is not None:
        payload["last_credits"] = float(credits)
    save_settings(payload)


def save_validation_state(state: str, *, credits: float | None = None, message: str = "") -> None:
    payload: dict[str, Any] = {
        "key_validation_state": str(state or "unknown"),
        "key_validated_at": int(time.time()),
        "key_validation_message": str(message or ""),
    }
    if credits is not None:
        payload["last_credits"] = float(credits)
    save_settings(payload)


def clear_api_key() -> None:
    path = settings_path()
    with _LOCK:
        current = load_settings()
        for key in (
            "api_key", "key_saved_at", "key_validation_state", "key_validated_at",
            "key_validation_message", "last_credits",
        ):
            current.pop(key, None)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(path)


def get_api_key() -> str:
    return (os.getenv("KIE_API_KEY", "") or str(load_settings().get("api_key") or "")).strip()


def mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    tail = key[-4:] if len(key) >= 4 else key
    return f"••••••••••••{tail}"


def public_status() -> dict[str, Any]:
    settings = load_settings()
    env_key = os.getenv("KIE_API_KEY", "").strip()
    key = env_key or str(settings.get("api_key") or "").strip()
    source = "environment" if env_key else ("saved" if settings.get("api_key") else "none")
    state = str(settings.get("key_validation_state") or ("configured" if key else "not_configured"))
    if env_key:
        state = "environment"
    return {
        "configured": bool(key),
        "source": source,
        "masked_key": mask_api_key(key),
        "validation_state": state,
        "validation_message": str(settings.get("key_validation_message") or ""),
        "validated_at": int(settings.get("key_validated_at") or 0),
        "last_credits": settings.get("last_credits"),
        "settings_path": str(settings_path()),
    }

