"""Immutable generation receipts kept outside the extension installation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..kie.settings import settings_path
from .characters import _slug


def recipes_root() -> Path:
    return settings_path().parent / "recipes"


def _json_value(text: str, label: str):
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON.") from exc


def _recipes() -> dict[str, Path]:
    root = recipes_root()
    if not root.is_dir():
        return {}
    return {path.stem: path for path in sorted(root.glob("*.json")) if path.is_file()}


class KIESaveGenerationRecipeNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "save_recipe"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("recipe_id", "recipe_json")
    OUTPUT_NODE = True
    DESCRIPTION = "Save model, prompt, camera, references, task ID, result URLs, and confirmed spend. No API key is stored."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("STRING", {"default": ""}),
            "prompt": ("STRING", {"default": "", "multiline": True}),
            "task_id": ("STRING", {"default": ""}),
            "credits_consumed": ("FLOAT", {"default": 0.0, "min": 0.0}),
        }, "optional": {
            "camera_plan_json": ("STRING", {"default": "{}", "multiline": True}),
            "references_json": ("STRING", {"default": "[]", "multiline": True}),
            "result_urls_json": ("STRING", {"default": "[]", "multiline": True}),
        }}

    def save_recipe(self, model, prompt, task_id, credits_consumed,
                    camera_plan_json="{}", references_json="[]", result_urls_json="[]"):
        model, prompt, task_id = (str(v or "").strip() for v in (model, prompt, task_id))
        if not model or not prompt:
            raise ValueError("A recipe needs the exact model and prompt.")
        if any(len(v) > 30000 for v in (prompt, camera_plan_json, references_json, result_urls_json)):
            raise ValueError("A recipe field exceeds 30,000 characters; split or summarize external metadata.")
        cost = float(credits_consumed)
        if not 0 <= cost < 1_000_000:
            raise ValueError("Confirmed credit spend must be a finite nonnegative number.")
        camera = _json_value(camera_plan_json, "camera_plan_json")
        references = _json_value(references_json, "references_json")
        urls = _json_value(result_urls_json, "result_urls_json")
        if not isinstance(camera, (dict, list)) or not isinstance(references, list) or not isinstance(urls, list):
            raise ValueError("Camera plan must be an object or array; references and result URLs must be arrays.")
        content = {"schema_version": 1, "model": model, "prompt": prompt, "task_id": task_id,
                   "credits_consumed": cost, "camera_plan": camera, "references": references,
                   "result_urls": urls}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        recipe_id = f"task-{_slug(task_id)}" if task_id else f"draft-{digest[:20]}"
        root = recipes_root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{recipe_id}.json"
        if path.exists():
            existing = _json_value(path.read_text(encoding="utf-8"), "saved recipe")
            if existing.get("content_sha256") != digest:
                raise ValueError("This task already has a different saved recipe. Keep the original record and inspect the discrepancy.")
            return (recipe_id, json.dumps(existing, ensure_ascii=False, indent=2))
        record = {**content, "recipe_id": recipe_id, "content_sha256": digest,
                  "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        partial = root / f".{recipe_id}.{digest[:8]}.saving"
        if partial.exists():
            raise ValueError("An incomplete recipe save exists; inspect it before retrying.")
        partial.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        partial.replace(path)
        return (recipe_id, json.dumps(record, ensure_ascii=False, indent=2))


class KIELoadGenerationRecipeNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "load_recipe"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model", "prompt", "task_id", "recipe_json")
    DESCRIPTION = "Load a saved generation record for review or manual recreation. Loading does not generate media."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"recipe_id": (list(_recipes()) or ["(no saved recipes)"],)}}

    def load_recipe(self, recipe_id):
        path = _recipes().get(recipe_id)
        if path is None:
            raise ValueError("Recipe not found. Save one, then refresh or re-add this node.")
        record = _json_value(path.read_text(encoding="utf-8"), "saved recipe")
        content = {k: record[k] for k in ("schema_version", "model", "prompt", "task_id", "credits_consumed",
                                          "camera_plan", "references", "result_urls") if k in record}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if digest != record.get("content_sha256"):
            raise ValueError("Saved recipe content has changed since creation.")
        return (record["model"], record["prompt"], record["task_id"], json.dumps(record, ensure_ascii=False, indent=2))


RECIPE_CLASS_MAPPINGS = {
    "KIE_Next_Save_Generation_Recipe": KIESaveGenerationRecipeNode,
    "KIE_Next_Load_Generation_Recipe": KIELoadGenerationRecipeNode,
}
RECIPE_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Save_Generation_Recipe": "KIE • Save Generation Recipe",
    "KIE_Next_Load_Generation_Recipe": "KIE • Load Generation Recipe",
}
