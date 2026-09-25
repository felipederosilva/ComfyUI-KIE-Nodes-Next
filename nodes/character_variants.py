"""Immutable approved looks linked to a fixed Character Pack identity."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..kie.media import bytes_to_image_tensor, image_tensor_to_png_bytes
from ..kie.settings import settings_path
from .characters import _read_manifest, _slug, character_packs_root


def variants_root() -> Path:
    return settings_path().parent / "character_variants"


def _parent(pack: dict) -> tuple[Path, dict]:
    if not isinstance(pack, dict) or not isinstance(pack.get("manifest"), dict):
        raise ValueError("Connect a loaded Character Pack.")
    directory = Path(str(pack.get("directory") or "")).resolve()
    if directory.parent != character_packs_root().resolve():
        raise ValueError("Character Pack is outside the active Comfy user library.")
    manifest = _read_manifest(directory)
    if manifest.get("content_sha256") != pack["manifest"].get("content_sha256"):
        raise ValueError("Character Pack identity changed since this workflow was built.")
    return directory, manifest


def _variant_manifest(directory: Path) -> dict:
    try:
        record = json.loads((directory / "variant.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Character variant manifest is missing or invalid.") from exc
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Unsupported Character variant manifest.")
    return record


def _variant_prompt(parent: dict, record: dict) -> str:
    identity = parent.get("identity") or {}
    return "\n".join(filter(None, (
        f"Character identity: {identity.get('description', '')}",
        f"Visual style: {identity.get('visual_style', '')}" if identity.get("visual_style") else "",
        f"Preserve identity: {identity.get('continuity_rules', '')}" if identity.get("continuity_rules") else "",
        f"Approved look {record['name']} v{record['version']}: {record['appearance']}",
        f"Scene allowance: {record['scene_allowance']}" if record.get("scene_allowance") else "",
    )))


class KIESaveCharacterVariantNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "save_variant"
    RETURN_TYPES = ("CHARACTER_VARIANT", "STRING")
    RETURN_NAMES = ("character_variant", "variant_prompt")
    OUTPUT_NODE = True
    DESCRIPTION = "Save an approved outfit or appearance as a versioned child of an immutable Character Pack."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "character_pack": ("CHARACTER_PACK",),
            "variant_name": ("STRING", {"default": "Day look"}),
            "version": ("STRING", {"default": "1"}),
            "appearance": ("STRING", {"default": "", "multiline": True}),
            "approved_image": ("IMAGE",),
        }, "optional": {"scene_allowance": ("STRING", {"default": "", "multiline": True})}}

    def save_variant(self, character_pack, variant_name, version, appearance, approved_image, scene_allowance=""):
        _, parent = _parent(character_pack)
        name, version, appearance = (str(v or "").strip() for v in (variant_name, version, appearance))
        if not all((name, version, appearance)):
            raise ValueError("Variant name, version, and appearance are required.")
        if getattr(approved_image, "ndim", 0) != 4 or approved_image.shape[0] != 1:
            raise ValueError("A Character variant requires exactly one approved IMAGE.")
        image = image_tensor_to_png_bytes(approved_image)
        parent_id = str(parent["pack_id"])
        key = f"{_slug(name)}__v{_slug(version)}"
        root = variants_root() / parent_id
        record = {"schema_version": 1, "parent_pack_id": parent_id,
                  "parent_content_sha256": parent["content_sha256"],
                  "name": name, "version": version, "appearance": appearance,
                  "scene_allowance": str(scene_allowance or "").strip(),
                  "reference_image": "approved.png", "reference_sha256": hashlib.sha256(image).hexdigest()}
        checksum = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        record.update({"content_sha256": checksum, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        root.mkdir(parents=True, exist_ok=True)
        target = root / key
        if target.exists():
            existing = _variant_manifest(target)
            if existing.get("content_sha256") != checksum:
                raise ValueError("This Character variant version already has different content. Create a new version.")
            return ({"directory": str(target), "manifest": existing}, _variant_prompt(parent, existing))
        staging = root / f".{key}.saving"
        if staging.exists():
            raise ValueError("An incomplete variant save exists; inspect it before retrying.")
        staging.mkdir()
        (staging / "approved.png").write_bytes(image)
        (staging / "variant.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.replace(target)
        return ({"directory": str(target), "manifest": record}, _variant_prompt(parent, record))


class KIELoadCharacterVariantNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "load_variant"
    RETURN_TYPES = ("IMAGE", "STRING", "CHARACTER_VARIANT")
    RETURN_NAMES = ("approved_image", "variant_prompt", "character_variant")
    DESCRIPTION = "Load one saved look without changing the underlying Character Pack identity."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"character_pack": ("CHARACTER_PACK",),
                             "variant_name": ("STRING", {"default": "Day look"}),
                             "version": ("STRING", {"default": "1"})}}

    def load_variant(self, character_pack, variant_name, version):
        _, parent = _parent(character_pack)
        root = variants_root() / str(parent["pack_id"])
        directory = (root / f"{_slug(variant_name)}__v{_slug(version)}").resolve()
        if directory.parent != root.resolve():
            raise ValueError("Character variant is outside its library.")
        record = _variant_manifest(directory)
        if (record.get("parent_pack_id") != parent["pack_id"] or
                record.get("parent_content_sha256") != parent["content_sha256"] or
                record.get("name") != str(variant_name).strip() or
                record.get("version") != str(version).strip()):
            raise ValueError("Character variant does not match the selected identity and version.")
        path = (directory / "approved.png").resolve()
        if path.parent != directory or not path.is_file():
            raise ValueError("Approved Character variant image is missing.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != record.get("reference_sha256"):
            raise ValueError("Approved Character variant image changed since save.")
        payload = {"directory": str(directory), "manifest": record}
        return (bytes_to_image_tensor(content), _variant_prompt(parent, record), payload)


VARIANT_CLASS_MAPPINGS = {
    "KIE_Next_Save_Character_Variant": KIESaveCharacterVariantNode,
    "KIE_Next_Load_Character_Variant": KIELoadCharacterVariantNode,
}
VARIANT_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Save_Character_Variant": "KIE • Save Character Variant",
    "KIE_Next_Load_Character_Variant": "KIE • Load Character Variant",
}
