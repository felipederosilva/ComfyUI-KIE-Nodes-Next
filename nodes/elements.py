"""Versioned local references for places, props, and visual styles."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..kie.media import bytes_to_image_tensor, image_tensor_to_png_bytes
from ..kie.settings import settings_path
from .characters import _slug


KINDS = ("location", "prop", "style")


def elements_root() -> Path:
    return settings_path().parent / "elements"


def _manifest(directory: Path) -> dict:
    try:
        data = json.loads((directory / "element.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Element manifest is missing or invalid.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("kind") not in KINDS:
        raise ValueError("Unsupported Element manifest.")
    return data


def _available() -> dict[str, Path]:
    root = elements_root()
    if not root.is_dir():
        return {}
    found = {}
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or not (directory / "element.json").is_file():
            continue
        try:
            record = _manifest(directory)
        except ValueError:
            continue
        found[f"{record['kind']} · {record['name']} · v{record['version']}"] = directory
    return found


def _prompt(record: dict) -> str:
    return "\n".join(filter(None, (
        f"{record['kind'].title()} reference: {record['name']}.",
        f"Visual definition: {record['description']}",
        f"Continuity rules: {record['continuity_rules']}" if record.get("continuity_rules") else "",
    )))


class KIESaveElementNode:
    CATEGORY = "KIE Next/Studio/Elements"
    FUNCTION = "save_element"
    RETURN_TYPES = ("KIE_ELEMENT", "STRING")
    RETURN_NAMES = ("element", "element_prompt")
    OUTPUT_NODE = True
    DESCRIPTION = "Save a versioned location, prop, or style in Comfy user data. Create a new version for changes."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "kind": (list(KINDS),),
            "name": ("STRING", {"default": "", "multiline": False}),
            "version": ("STRING", {"default": "1"}),
            "description": ("STRING", {"default": "", "multiline": True}),
        }, "optional": {
            "reference_image": ("IMAGE",),
            "continuity_rules": ("STRING", {"default": "", "multiline": True}),
        }}

    def save_element(self, kind, name, version, description, reference_image=None, continuity_rules=""):
        if kind not in KINDS:
            raise ValueError("Element kind must be location, prop, or style.")
        name, version, description = (str(value or "").strip() for value in (name, version, description))
        if not all((name, version, description)):
            raise ValueError("Element name, version, and description are required.")
        image_bytes = None
        if reference_image is not None:
            if getattr(reference_image, "ndim", 0) != 4 or reference_image.shape[0] != 1:
                raise ValueError("Element reference must be exactly one IMAGE.")
            image_bytes = image_tensor_to_png_bytes(reference_image)
        if kind in ("location", "prop") and image_bytes is None:
            raise ValueError(f"A {kind} needs one approved reference image.")
        key = f"{kind}__{_slug(name)}__v{_slug(version)}"
        record = {"schema_version": 1, "kind": kind, "name": name, "version": version,
                  "description": description, "continuity_rules": str(continuity_rules or "").strip(),
                  "reference_image": "reference.png" if image_bytes else ""}
        record["reference_sha256"] = hashlib.sha256(image_bytes).hexdigest() if image_bytes else ""
        content = dict(record)
        checksum = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        record.update({"content_sha256": checksum, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        root = elements_root()
        root.mkdir(parents=True, exist_ok=True)
        target = root / key
        if target.exists():
            existing = _manifest(target)
            if existing.get("content_sha256") != checksum:
                raise ValueError(f"Element {name} v{version} already exists with different content. Create a new version.")
            return ({"directory": str(target), "manifest": existing}, _prompt(existing))
        staging = root / f".{key}.saving"
        if staging.exists():
            raise ValueError("An incomplete Element save exists; inspect it before retrying.")
        staging.mkdir()
        if image_bytes:
            (staging / "reference.png").write_bytes(image_bytes)
        (staging / "element.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.replace(target)
        return ({"directory": str(target), "manifest": record}, _prompt(record))


class KIELoadElementNode:
    CATEGORY = "KIE Next/Studio/Elements"
    FUNCTION = "load_element"
    RETURN_TYPES = ("KIE_ELEMENT", "STRING")
    RETURN_NAMES = ("element", "element_prompt")
    DESCRIPTION = "Reuse a saved element and its visual continuity brief."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"element": (list(_available()) or ["(no saved Elements)"],)}}

    def load_element(self, element):
        directory = _available().get(element)
        if directory is None:
            raise ValueError("Element not found. Save it, then refresh or re-add this node.")
        record = _manifest(directory)
        return ({"directory": str(directory), "manifest": record}, _prompt(record))


class KIEElementReferenceNode:
    CATEGORY = "KIE Next/Studio/Elements"
    FUNCTION = "load_reference"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("reference_image", "element_prompt")
    DESCRIPTION = "Load the approved image of a location, prop, or style for a model that supports image references."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"element": ("KIE_ELEMENT",)}}

    def load_reference(self, element):
        if not isinstance(element, dict) or not isinstance(element.get("manifest"), dict):
            raise ValueError("Connect a saved or loaded Element.")
        directory = Path(str(element.get("directory") or "")).resolve()
        if directory.parent != elements_root().resolve():
            raise ValueError("Element is outside the active Comfy user library.")
        record = _manifest(directory)
        if record.get("content_sha256") != element["manifest"].get("content_sha256"):
            raise ValueError("Element reference does not match its saved version.")
        filename = record.get("reference_image")
        if not filename:
            raise ValueError("This style has no image. Use the Element prompt output or save a new version with an image.")
        path = (directory / filename).resolve()
        if path.parent != directory or not path.is_file():
            raise ValueError("Element reference image is missing or outside its folder.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != record.get("reference_sha256"):
            raise ValueError("Element reference image changed since this version was saved.")
        return (bytes_to_image_tensor(content), _prompt(record))


ELEMENT_CLASS_MAPPINGS = {
    "KIE_Next_Save_Element": KIESaveElementNode,
    "KIE_Next_Load_Element": KIELoadElementNode,
    "KIE_Next_Element_Reference": KIEElementReferenceNode,
}
ELEMENT_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Save_Element": "KIE • Save Element",
    "KIE_Next_Load_Element": "KIE • Load Element",
    "KIE_Next_Element_Reference": "KIE • Element Reference",
}
