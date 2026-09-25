"""Persistent visual comparison of controlled, manually generated variations."""
from __future__ import annotations

import json
import textwrap

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .consistency_board import _image
from .media import KIEPersistentPreviewImageNode


def build_variation_board(matrix_json: str, images: list[tuple[int, object]]) -> tuple[torch.Tensor, str]:
    try:
        matrix = json.loads(matrix_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Connect a Variation Matrix JSON output.") from exc
    takes = matrix.get("takes") if isinstance(matrix, dict) else None
    if not isinstance(takes, list) or not 1 <= len(takes) <= 4 or any(not isinstance(take, dict) for take in takes):
        raise ValueError("Variation Matrix must contain one to four takes.")
    selected = []
    for index, value in images:
        match = next((take for take in takes if take.get("take") == index), None)
        if match is None:
            raise ValueError(f"Take {index} is not defined in this Variation Matrix.")
        selected.append((index, str(match.get("delta") or ""), _image(value, f"take_{index}")))
    if not selected:
        raise ValueError("Connect at least one generated image to compare.")
    columns = 2 if len(selected) > 1 else 1
    rows = (len(selected) + columns - 1) // columns
    card_width, card_height = 360, 355
    board = Image.new("RGB", (columns * card_width, rows * card_height), "#151a20")
    draw = ImageDraw.Draw(board)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for position, (index, delta, source) in enumerate(selected):
        x, y = position % columns * card_width, position // columns * card_height
        draw.rectangle((x + 4, y + 4, x + card_width - 4, y + card_height - 4), fill="#28333e")
        preview = ImageOps.contain(source, (card_width - 18, 270))
        board.paste(preview, (x + (card_width - preview.width) // 2, y + 8 + (270 - preview.height) // 2))
        draw.text((x + 12, y + 288), f"TAKE {index}", font=font, fill="#f2cf81")
        for line_number, line in enumerate(textwrap.wrap(delta, width=42)[:2]):
            draw.text((x + 12, y + 311 + line_number * 19), line, font=font, fill="#e6edf3")
    tensor = torch.from_numpy(np.asarray(board, dtype=np.float32).copy() / 255).unsqueeze(0)
    report = {"schema_version": 1, "compared": [{"take": number, "delta": delta} for number, delta, _ in selected],
              "method": "Editor visual comparison. Matching base prompt/settings must be verified from generation recipes; no automatic quality score."}
    return tensor, json.dumps(report, ensure_ascii=False)


class KIEVariationBoardNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "compare"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("comparison_board", "comparison_json", "saved_files_json")
    OUTPUT_NODE = True
    DESCRIPTION = "Compare up to four manually generated IMAGE results against one Variation Matrix. Saves a durable contact sheet; no model submissions or invented scores."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"matrix_json": ("STRING", {"forceInput": True}), "take_1_image": ("IMAGE",)},
                "optional": {f"take_{index}_image": ("IMAGE",) for index in range(2, 5)}}

    def compare(self, matrix_json, take_1_image, **kwargs):
        images = [(1, take_1_image)]
        images.extend((index, kwargs[f"take_{index}_image"]) for index in range(2, 5)
                      if kwargs.get(f"take_{index}_image") is not None)
        board, report = build_variation_board(matrix_json, images)
        saved = KIEPersistentPreviewImageNode().save_images(board, "KIE-Variations/Comparison")
        return {"ui": saved["ui"], "result": (board, report, saved["result"][1])}
