from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..kie.media import bytes_to_image_tensor, image_tensor_to_png_bytes
from ..kie.settings import settings_path


_ASSET_ROLES = ("portrait", "full_body", "profile", "expression_sheet")
_SCHEMA_VERSION = 1
_QA_CASES = {
    "portrait · front": ("portrait", "tight front-facing portrait, neutral expression, even soft light"),
    "portrait · three-quarter": ("portrait", "three-quarter face angle, calm expression, soft side light"),
    "portrait · profile": ("profile", "clean side profile, neutral expression, clear silhouette"),
    "full body · front": ("full_body", "full-body front view, relaxed standing pose, plain studio background"),
    "full body · wide frame": ("full_body", "wide environmental composition with the character small in frame; preserve body proportions and recognizable silhouette"),
    "camera · low angle": ("portrait", "low camera angle, face and distinctive features remain recognizable"),
    "camera · high angle": ("portrait", "high camera angle, face and distinctive features remain recognizable"),
    "continuity · changed scene": ("portrait", "new location, lighting, and wardrobe as requested; do not alter identity-defining facial or body traits"),
}


def character_packs_root() -> Path:
    """Keep reusable packs in Comfy's per-user KIE data, not in the plugin folder."""
    return settings_path().parent / "character_packs"


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise ValueError("Character name/version must include at least one letter or number.")
    return slug[:64].rstrip("-")


def _read_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "character.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Character Pack manifest is unavailable or invalid: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(f"Unsupported Character Pack manifest: {path}")
    return value


def _available_packs() -> dict[str, Path]:
    root = character_packs_root()
    if not root.is_dir():
        return {}
    found: dict[str, Path] = {}
    for directory in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not directory.is_dir() or not (directory / "character.json").is_file():
            continue
        try:
            manifest = _read_manifest(directory)
        except ValueError:
            continue
        label = f"{manifest.get('name', directory.name)} · v{manifest.get('version', '1')}"
        found[label] = directory
    return found


def _required_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required to save a Character Pack.")
    return text


class KIESaveCharacterPackNode:
    """Save an immutable, versioned set of approved identity references."""

    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "save_pack"
    RETURN_TYPES = ("CHARACTER_PACK", "STRING")
    RETURN_NAMES = ("character_pack", "manifest_json")
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Save a versioned Character Pack in Comfy's user data folder. Identical saves are safe; "
        "create a new version when approved identity or references change."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {"default": "My Character"}),
                "version": ("STRING", {"default": "1", "tooltip": "Use a new version for any approved identity/reference change."}),
                "identity_description": ("STRING", {"default": "", "multiline": True}),
                "visual_style": ("STRING", {"default": "", "multiline": True}),
                "continuity_rules": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "portrait": ("IMAGE",),
                "full_body": ("IMAGE",),
                "profile": ("IMAGE",),
                "expression_sheet": ("IMAGE",),
                "wardrobe_notes": ("STRING", {"default": "", "multiline": True}),
                "real_person_reference": ("BOOLEAN", {"default": False}),
                "consent_confirmed": ("BOOLEAN", {"default": False, "tooltip": "Required when references depict a real person."}),
            },
        }

    def save_pack(
        self, name, version, identity_description, visual_style, continuity_rules,
        portrait=None, full_body=None, profile=None, expression_sheet=None,
        wardrobe_notes="", real_person_reference=False, consent_confirmed=False,
    ):
        pack_name = _required_text(name, "Name")
        pack_version = _required_text(version, "Version")
        identity = _required_text(identity_description, "Identity description")
        if real_person_reference and not consent_confirmed:
            raise ValueError("Confirm permission to use the real person's likeness before saving this Character Pack.")
        directory_name = f"{_slug(pack_name)}__v{_slug(pack_version)}"
        root = character_packs_root()
        root.mkdir(parents=True, exist_ok=True)
        assets: dict[str, str] = {}
        asset_bytes: dict[str, bytes] = {}
        images = {
            "portrait": portrait,
            "full_body": full_body,
            "profile": profile,
            "expression_sheet": expression_sheet,
        }
        for role in _ASSET_ROLES:
            image = images[role]
            if image is None:
                continue
            if int(image.shape[0] if image.ndim == 4 else 1) != 1:
                raise ValueError(f"{role} accepts one approved image. Split image batches before saving the pack.")
            filename = f"{role}.png"
            asset_bytes[filename] = image_tensor_to_png_bytes(image)
            assets[role] = filename
        if "portrait" not in assets:
            raise ValueError("A canonical portrait image is required for every Character Pack.")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        identity_record = {
            "description": identity,
            "visual_style": str(visual_style or "").strip(),
            "continuity_rules": str(continuity_rules or "").strip(),
            "wardrobe_notes": str(wardrobe_notes or "").strip(),
        }
        content_record = {
            "name": pack_name,
            "version": pack_version,
            "identity": identity_record,
            "assets": {role: hashlib.sha256(asset_bytes[filename]).hexdigest() for role, filename in assets.items()},
            "real_person_reference": bool(real_person_reference),
            "consent_confirmed": bool(consent_confirmed),
        }
        checksum = hashlib.sha256(json.dumps(content_record, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        manifest = {
            "schema_version": _SCHEMA_VERSION,
            "pack_id": directory_name,
            "name": pack_name,
            "version": pack_version,
            "created_at": now,
            "identity": identity_record,
            "assets": assets,
            "real_person_reference": bool(real_person_reference),
            "consent_confirmed": bool(consent_confirmed),
            "content_sha256": checksum,
        }

        target = root / directory_name
        if target.exists():
            existing = _read_manifest(target)
            if existing.get("content_sha256") == checksum:
                payload = {"directory": str(target), "manifest": existing}
                return (payload, json.dumps(existing, ensure_ascii=False, indent=2))
            raise ValueError(
                f"Character Pack {pack_name} v{pack_version} already exists with different contents. "
                "Create a new version; saved versions are immutable."
            )

        # Build in a temporary sibling directory and publish atomically, so an
        # interrupted save cannot leave a half-valid pack visible in the picker.
        staging = root / f".{directory_name}.saving"
        if staging.exists():
            raise ValueError(f"An incomplete save already exists at {staging}; inspect it before retrying.")
        staging.mkdir()
        try:
            for filename, content in asset_bytes.items():
                (staging / filename).write_bytes(content)
            manifest_path = staging / "character.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            staging.replace(target)
        except Exception:
            # Retain staging data for recovery instead of deleting user media.
            raise

        payload = {"directory": str(target), "manifest": manifest}
        return (payload, json.dumps(manifest, ensure_ascii=False, indent=2))


class KIELoadCharacterPackNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "load_pack"
    RETURN_TYPES = ("CHARACTER_PACK", "STRING", "STRING")
    RETURN_NAMES = ("character_pack", "identity_prompt", "manifest_json")
    DESCRIPTION = "Load a saved, immutable Character Pack and emit its identity brief for use in downstream prompts."

    @classmethod
    def INPUT_TYPES(cls):
        packs = list(_available_packs())
        return {"required": {"character": (packs or ["(no saved Character Packs)"],)}}

    def load_pack(self, character):
        packs = _available_packs()
        if character not in packs:
            raise ValueError("No matching saved Character Pack. Save one first, then refresh/re-add this node.")
        directory = packs[character]
        manifest = _read_manifest(directory)
        payload = {"directory": str(directory), "manifest": manifest}
        identity = manifest.get("identity") or {}
        prompt = "\n".join(part for part in (
            f"Character identity: {identity.get('description', '')}".strip(),
            f"Visual style: {identity.get('visual_style', '')}".strip(),
            f"Continuity rules: {identity.get('continuity_rules', '')}".strip(),
        ) if not part.endswith(": "))
        return (payload, prompt, json.dumps(manifest, ensure_ascii=False, indent=2))


class KIECharacterReferenceNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "load_reference"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("reference_image", "character_prompt")
    DESCRIPTION = (
        "Load one approved view from a Character Pack. Connect the image only to model operations that document "
        "reference-image support; this does not itself guarantee identity lock."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character_pack": ("CHARACTER_PACK",),
                "view": (list(_ASSET_ROLES),),
                "wardrobe_or_scene_variation": ("STRING", {"default": "", "multiline": True}),
            },
        }

    def load_reference(self, character_pack, view, wardrobe_or_scene_variation=""):
        if not isinstance(character_pack, dict) or not isinstance(character_pack.get("manifest"), dict):
            raise ValueError("Connect a loaded KIE Character Pack.")
        manifest = character_pack["manifest"]
        relative = (manifest.get("assets") or {}).get(view)
        if not relative:
            available = ", ".join((manifest.get("assets") or {}).keys()) or "none"
            raise ValueError(f"This pack has no {view} reference. Available views: {available}.")
        directory = Path(str(character_pack.get("directory") or "")).resolve()
        image_path = (directory / relative).resolve()
        if directory not in image_path.parents or not image_path.is_file():
            raise ValueError("The selected Character Pack reference is missing or outside its pack folder.")
        from PIL import Image
        import io
        with Image.open(image_path) as image:
            stream = io.BytesIO()
            image.convert("RGB").save(stream, format="PNG")
            tensor = bytes_to_image_tensor(stream.getvalue())

        identity = manifest.get("identity") or {}
        prompt_parts = [
            f"Character identity: {identity.get('description', '')}".strip(),
            f"Visual style: {identity.get('visual_style', '')}".strip(),
            f"Continuity rules: {identity.get('continuity_rules', '')}".strip(),
        ]
        variation = str(wardrobe_or_scene_variation or "").strip()
        if variation:
            prompt_parts.append(f"Allowed scene/wardrobe variation: {variation}")
        return (tensor, "\n".join(part for part in prompt_parts if not part.endswith(": ")))


class KIECharacterConsistencyPlanNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "build_plan"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("case_prompt", "reference_view", "test_matrix_json")
    DESCRIPTION = (
        "Build a reviewable multi-shot consistency test plan from a saved Character Pack. "
        "This node does not generate media; run each case through an operation that documents reference-image support."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character_pack": ("CHARACTER_PACK",),
                "test_case": (list(_QA_CASES),),
            },
            "optional": {
                "variation_notes": ("STRING", {"default": "", "multiline": True}),
            },
        }

    def build_plan(self, character_pack, test_case, variation_notes=""):
        if not isinstance(character_pack, dict) or not isinstance(character_pack.get("manifest"), dict):
            raise ValueError("Connect a loaded KIE Character Pack.")
        manifest = character_pack["manifest"]
        identity = manifest.get("identity") or {}
        matrix = []
        for case_name, (view, framing) in _QA_CASES.items():
            if view not in (manifest.get("assets") or {}):
                continue
            prompt_parts = [
                f"Use the attached {view.replace('_', ' ')} image as the identity reference for {manifest.get('name', 'the character')}; depict the same character, not a redesign.",
                f"Identity anchors: {identity.get('description', '')}",
                f"Visual style: {identity.get('visual_style', '')}",
                f"Preserve: {identity.get('continuity_rules', '')}",
                f"Test condition: {framing}.",
            ]
            notes = str(variation_notes or "").strip()
            if notes and case_name == "continuity · changed scene":
                prompt_parts.append(f"Allowed variation for this test: {notes}")
            matrix.append({"case": case_name, "reference_view": view, "prompt": "\n".join(p for p in prompt_parts if not p.endswith(": "))})

        selected = next((item for item in matrix if item["case"] == test_case), None)
        if selected is None:
            raise ValueError(f"The selected test case needs a {dict(_QA_CASES).get(test_case, ('reference',))[0]} view, which this pack does not contain.")
        return (selected["prompt"], selected["reference_view"], json.dumps(matrix, ensure_ascii=False, indent=2))


CHARACTER_CLASS_MAPPINGS = {
    "KIE_Next_Save_Character_Pack": KIESaveCharacterPackNode,
    "KIE_Next_Load_Character_Pack": KIELoadCharacterPackNode,
    "KIE_Next_Character_Reference": KIECharacterReferenceNode,
    "KIE_Next_Character_Consistency_Plan": KIECharacterConsistencyPlanNode,
}

CHARACTER_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Save_Character_Pack": "KIE • Save Character Pack",
    "KIE_Next_Load_Character_Pack": "KIE • Load Character Pack",
    "KIE_Next_Character_Reference": "KIE • Character Reference",
    "KIE_Next_Character_Consistency_Plan": "KIE • Character Consistency Test Plan",
}
