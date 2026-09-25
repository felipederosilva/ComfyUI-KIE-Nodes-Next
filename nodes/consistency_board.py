"""Persistent side-by-side visual QA board for character and element references."""
from __future__ import annotations

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .media import KIEPersistentPreviewImageNode


CARD_WIDTH, CARD_HEIGHT = 300, 390
PHOTO_HEIGHT = 320


def _image(value, name):
    if not isinstance(value, torch.Tensor) or value.ndim != 4 or value.shape[0] != 1 or value.shape[-1] not in (3, 4):
        raise ValueError(f"{name} must be one RGB/RGBA IMAGE.")
    if not torch.isfinite(value).all():
        raise ValueError(f"{name} contains non-finite pixels.")
    pixels = (value[0].detach().cpu().clamp(0, 1).numpy() * 255).round().astype(np.uint8)
    return Image.fromarray(pixels, "RGB" if pixels.shape[-1] == 3 else "RGBA").convert("RGB")


def build_consistency_board(reference, candidates: list[tuple[str, object]]) -> torch.Tensor:
    if not 1 <= len(candidates) <= 4:
        raise ValueError("Compare between one and four candidate images.")
    cards = [("APPROVED REFERENCE", reference), *candidates]
    board = Image.new("RGB", (len(cards) * CARD_WIDTH, CARD_HEIGHT), "#151a20")
    draw = ImageDraw.Draw(board)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for index, (label, value) in enumerate(cards):
        source = _image(value, "reference" if index == 0 else f"candidate_{index}")
        preview = ImageOps.contain(source, (CARD_WIDTH - 20, PHOTO_HEIGHT))
        x = index * CARD_WIDTH
        draw.rectangle((x + 5, 5, x + CARD_WIDTH - 5, CARD_HEIGHT - 5), fill="#28333e")
        board.paste(preview, (x + (CARD_WIDTH - preview.width) // 2, 10 + (PHOTO_HEIGHT - preview.height) // 2))
        caption = str(label or f"TAKE {index}").strip()[:30]
        draw.text((x + 12, 345), caption, font=font, fill="#f0f4f7" if index else "#f2cf81")
    return torch.from_numpy(np.asarray(board, dtype=np.float32).copy() / 255.0).unsqueeze(0)


class KIEConsistencyBoardNode:
    CATEGORY = "KIE Next/Studio/Characters"
    FUNCTION = "compare"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("comparison_board", "saved_files_json")
    OUTPUT_NODE = True
    DESCRIPTION = "Compare an approved reference with up to four outputs on a persistent local board. Human review; no identity score."

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(2, 5):
            optional[f"candidate_{i}"] = ("IMAGE",)
            optional[f"label_{i}"] = ("STRING", {"default": f"TAKE {i}"})
        return {"required": {
            "approved_reference": ("IMAGE",),
            "candidate_1": ("IMAGE",),
            "label_1": ("STRING", {"default": "TAKE 1"}),
        }, "optional": optional}

    def compare(self, approved_reference, candidate_1, label_1="TAKE 1", **kwargs):
        candidates = [(label_1, candidate_1)]
        for i in range(2, 5):
            image = kwargs.get(f"candidate_{i}")
            if image is not None:
                candidates.append((kwargs.get(f"label_{i}", f"TAKE {i}"), image))
        board = build_consistency_board(approved_reference, candidates)
        saved = KIEPersistentPreviewImageNode().save_images(board, "KIE-Consistency/Comparison")
        return {"ui": saved["ui"], "result": (board, saved["result"][1])}
