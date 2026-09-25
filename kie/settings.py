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


def save_last_credits(credits: float) -> None:
    """Persist the most recently fetched live account balance for Settings UI."""
    save_settings({"last_credits": float(credits), "last_credits_checked_at": int(time.time())})


def record_credit_usage(spent: float, balance: float | None = None, *, receipt_id: str = "") -> dict[str, Any]:
    """Track KIE-reported spending by this ComfyUI profile (not account-wide history)."""
    now = int(time.time())
    with _LOCK:
        current = load_settings()
        receipts = current.get("credit_usage_receipts")
        if not isinstance(receipts, dict):
            receipts = {}
        key = str(receipt_id or "").strip()
        amount = max(0.0, float(spent or 0.0))
        if key and key in receipts:
            amount = 0.0
        elif key and amount > 0:
            receipts[key] = now
            current["credit_usage_receipts"] = receipts
        total = float(current.get("tracked_credits_spent") or 0.0) + amount
        current["tracked_credits_spent"] = total
        current.setdefault("credit_usage_started_at", now)
        current["credit_usage_updated_at"] = now
        if balance is not None and float(balance) >= 0:
            current["last_credits"] = float(balance)
            current["last_credits_checked_at"] = now
        temp = settings_path().with_suffix(".tmp")
        temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(settings_path())
        try:
            os.chmod(settings_path(), 0o600)
        except OSError:
            pass
        return {
            "tracked_credits_spent": total,
            "credit_usage_started_at": int(current.get("credit_usage_started_at") or now),
            "credit_usage_updated_at": now,
            "last_credits": current.get("last_credits"),
            "last_credits_checked_at": current.get("last_credits_checked_at"),
        }


def credit_usage_status() -> dict[str, Any]:
    settings = load_settings()
    return {
        "tracked_credits_spent": float(settings.get("tracked_credits_spent") or 0.0),
        "credit_usage_started_at": int(settings.get("credit_usage_started_at") or 0),
        "credit_usage_updated_at": int(settings.get("credit_usage_updated_at") or 0),
        "last_credits": settings.get("last_credits"),
        "last_credits_checked_at": int(settings.get("last_credits_checked_at") or 0),
    }


def clear_api_key() -> None:
    path = settings_path()
    with _LOCK:
        current = load_settings()
        for key in (
            "api_key", "key_saved_at", "key_validation_state", "key_validated_at",
            "key_validation_message", "last_credits", "last_credits_checked_at",
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
        "last_credits_checked_at": int(settings.get("last_credits_checked_at") or 0),
        **credit_usage_status(),
        "settings_path": str(settings_path()),
    }

