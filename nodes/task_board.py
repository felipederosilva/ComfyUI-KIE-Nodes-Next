"""Read-only status board for KIE task IDs supplied by the editor."""
from __future__ import annotations

import json

from ..kie.client import KIEClient
from ..kie.helpers import make_client
from ..kie.task_history import recent_tasks


def task_board(client, task_ids: str) -> tuple[str, str]:
    ids = list(dict.fromkeys(part.strip() for part in str(task_ids or "").replace("\n", ",").split(",") if part.strip()))
    if not ids:
        ids = [str(row.get("task_id") or "") for row in recent_tasks(20) if row.get("task_id")]
    if not ids or len(ids) > 20 or any(len(task_id) > 200 for task_id in ids):
        raise ValueError("No local task IDs yet. Enter 1–20 KIE task IDs, separated by commas or new lines.")
    rows = []
    for task_id in ids:
        try:
            data = client.get_task(task_id)
            state = str(data.get("state") or "unknown")
            progress = data.get("progress")
            urls = KIEClient.extract_result_urls(data)
            rows.append({"task_id": task_id, "state": state,
                         "progress": progress if isinstance(progress, (int, float)) and not isinstance(progress, bool) else None,
                         "result_urls": urls, "failure": str(data.get("failMsg") or data.get("failCode") or ""),
                         "credits_consumed": float(data.get("creditsConsumed") or 0)})
        except Exception as exc:
            rows.append({"task_id": task_id, "state": "lookup_error", "progress": None,
                         "result_urls": [], "failure": str(exc), "credits_consumed": 0.0})
    lines = [f"{row['task_id']}: {row['state']}" +
             (f" ({row['progress']}%)" if row['progress'] is not None else "") +
             (f" — {row['failure']}" if row['failure'] else "") +
             (f" — {len(row['result_urls'])} result(s)" if row['result_urls'] else "")
             for row in rows]
    return json.dumps({"schema_version": 1, "tasks": rows,
                       "read_only": True, "source": "KIE recordInfo by explicit task ID"}, ensure_ascii=False), "\n".join(lines)


class KIETaskBoardNode:
    CATEGORY = "KIE Next/Utility/Tasks"
    FUNCTION = "refresh"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tasks_json", "status_summary")
    DESCRIPTION = "Refresh recent KIE Next task IDs automatically, or enter 1–20 IDs. Read-only: shows status, failure and result URLs without resubmitting or downloading media."
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"task_ids": ("STRING", {"default": "", "multiline": True})},
                "optional": {"config": ("KIE_CONFIG",)}}

    def refresh(self, task_ids, config=None):
        data, summary = task_board(make_client(config), task_ids)
        return {"ui": {"text": [summary]}, "result": (data, summary)}
