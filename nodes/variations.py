"""Comparable prompt variations with one explicitly changed condition per take."""
from __future__ import annotations

import json


def variation_matrix(base_prompt: str, fixed_constraints: str, changes: list[str]) -> tuple:
    base = str(base_prompt or "").strip()
    if not base:
        raise ValueError("A variation matrix needs a base prompt.")
    if len(base) > 15000:
        raise ValueError("Base prompt exceeds 15,000 characters.")
    fixed = str(fixed_constraints or "").strip()
    if not any(str(change or "").strip() for change in changes):
        raise ValueError("Add at least one deliberate variation.")
    prompts, records = [], []
    for index, raw in enumerate(changes, 1):
        change = str(raw or "").strip()
        if not change:
            prompts.append("")
            continue
        if len(change) > 3000:
            raise ValueError(f"Variation {index} exceeds 3,000 characters.")
        prompt = "\n\n".join(filter(None, (base, f"Keep constant across takes: {fixed}" if fixed else "",
                                             f"Change for take {index} only: {change}")))
        prompts.append(prompt)
        records.append({"take": index, "delta": change, "prompt": prompt})
    manifest = {"schema_version": 1, "base_prompt": base, "fixed_constraints": fixed,
                "takes": records, "method": "Connect each prompt to the same model/settings and compare outputs; provider seeds and reference behavior vary by model."}
    return (*prompts, json.dumps(manifest, ensure_ascii=False))


class KIEVariationMatrixNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("take_1_prompt", "take_2_prompt", "take_3_prompt", "take_4_prompt", "matrix_json")
    DESCRIPTION = "Prepare up to four comparable prompts by changing one specified condition per take. Does not submit generations."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"base_prompt": ("STRING", {"default": "", "multiline": True}),
                             "take_1_change": ("STRING", {"default": "wide framing", "multiline": True})},
                "optional": {"fixed_constraints": ("STRING", {"default": "same character, wardrobe, location, and lighting", "multiline": True}),
                             "take_2_change": ("STRING", {"default": "medium framing", "multiline": True}),
                             "take_3_change": ("STRING", {"default": "close-up framing", "multiline": True}),
                             "take_4_change": ("STRING", {"default": "", "multiline": True})}}

    def build(self, base_prompt, take_1_change, fixed_constraints="", take_2_change="",
              take_3_change="", take_4_change=""):
        return variation_matrix(base_prompt, fixed_constraints,
                                [take_1_change, take_2_change, take_3_change, take_4_change])
