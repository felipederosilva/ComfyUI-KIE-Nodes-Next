"""Small local task-ID journal for recovery and status review; never stores API keys."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .settings import _user_config_dir


_LOCK = threading.RLock()


def _path() -> Path:
    return _user_config_dir() / "task_history.json"


def recent_tasks(limit: int = 20) -> list[dict]:
    path = _path()
    with _LOCK:
        if not path.is_file():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        rows = value.get("tasks") if isinstance(value, dict) else None
        return [row for row in rows[:max(0, min(int(limit), 500))] if isinstance(row, dict)] if isinstance(rows, list) else []


def record_task(task_id: str, model: str, state: str, *, error: str = "", credits: float | None = None) -> None:
    task_id = str(task_id or "").strip()
    if not task_id or len(task_id) > 200:
        return
    now = int(time.time())
    with _LOCK:
        rows = recent_tasks(500)
        old = next((row for row in rows if row.get("task_id") == task_id), {})
        row = {"task_id": task_id, "model": str(model or old.get("model") or "")[:200],
               "state": str(state or "unknown")[:40], "submitted_at": old.get("submitted_at") or now,
               "updated_at": now, "error": str(error or "")[:500]}
        if credits is not None:
            row["credits_consumed"] = max(0.0, float(credits))
        elif "credits_consumed" in old:
            row["credits_consumed"] = old["credits_consumed"]
        rows = [row] + [entry for entry in rows if entry.get("task_id") != task_id]
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.tmp")
        temp.write_text(json.dumps({"schema_version": 1, "tasks": rows[:500]}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
