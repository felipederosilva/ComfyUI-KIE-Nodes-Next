"""Output node for editable planning text that must be reviewed before spending."""
from __future__ import annotations


class KIETextReviewNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "show"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_NODE = True
    DESCRIPTION = "Display a connected planning brief or cue sheet for review. Does not call KIE or spend credits."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"forceInput": True}),
                             "label": ("STRING", {"default": "Review before generation"})}}

    def show(self, text, label="Review before generation"):
        value = str(text or "")
        return {"ui": {"kie_review_text": [{"label": str(label or "Review"), "text": value}]},
                "result": (value,)}
