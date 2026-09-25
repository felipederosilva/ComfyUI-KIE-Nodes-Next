"""Local storyboard review from a Shot Sequence and optional approved frames."""
from __future__ import annotations

import json
import textwrap

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .media import KIEPersistentPreviewImageNode


CARD_W, CARD_H = 512, 420
IMAGE_H = 256
MARGIN = 18


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _frame_image(value, index: int) -> Image.Image:
    if not isinstance(value, torch.Tensor) or value.ndim != 4 or value.shape[0] != 1:
        raise ValueError(f"hero_frame_{index} must be one ComfyUI IMAGE, not an image batch.")
    if value.shape[-1] not in (3, 4):
        raise ValueError(f"hero_frame_{index} must have RGB or RGBA channels.")
    if not torch.isfinite(value).all():
        raise ValueError(f"hero_frame_{index} contains non-finite pixels.")
    pixels = (value[0].detach().cpu().clamp(0, 1).numpy() * 255).round().astype(np.uint8)
    return Image.fromarray(pixels, "RGB" if pixels.shape[-1] == 3 else "RGBA").convert("RGB")


def build_storyboard(sequence: str, frames: dict[int, object]) -> tuple[torch.Tensor, dict]:
    try:
        shots = json.loads(sequence)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Connect a valid Shot Sequence JSON array.") from exc
    if not isinstance(shots, list) or not 1 <= len(shots) <= 6:
        raise ValueError("A storyboard needs 1 to 6 shots from Shot Sequence.")
    extras = set(frames) - set(range(1, len(shots) + 1))
    if extras:
        raise ValueError(f"A hero frame is connected beyond the {len(shots)} planned shots.")
    columns = min(len(shots), 3)
    rows = (len(shots) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * CARD_W, rows * CARD_H), "#10161d")
    draw = ImageDraw.Draw(sheet)
    title_font, body_font = _font(21), _font(17)
    review = []
    for i, shot in enumerate(shots, 1):
        if not isinstance(shot, dict) or not isinstance(shot.get("prompt"), str) or not shot["prompt"].strip():
            raise ValueError(f"Shot {i} needs a text prompt.")
        x, y = ((i - 1) % columns) * CARD_W, ((i - 1) // columns) * CARD_H
        draw.rounded_rectangle((x + 8, y + 8, x + CARD_W - 8, y + CARD_H - 8), radius=13, fill="#242d37")
        draw.rectangle((x + MARGIN, y + MARGIN, x + CARD_W - MARGIN, y + MARGIN + IMAGE_H), fill="#344454")
        has_frame = i in frames
        if has_frame:
            preview = ImageOps.contain(_frame_image(frames[i], i), (CARD_W - 2 * MARGIN, IMAGE_H))
            sheet.paste(preview, (x + (CARD_W - preview.width) // 2, y + MARGIN + (IMAGE_H - preview.height) // 2))
        else:
            draw.text((x + 176, y + 136), "NO HERO FRAME", font=title_font, fill="#abb8c6")
        camera = shot.get("camera") if isinstance(shot.get("camera"), dict) else {}
        duration = shot.get("duration", "?")
        draw.text((x + MARGIN, y + 287), f"SHOT {i:02d}  |  {duration}s", font=title_font, fill="#f3f5f7")
        line = " ".join(textwrap.wrap(shot["prompt"].strip(), width=62)[:2])
        draw.text((x + MARGIN, y + 320), line[:72], font=body_font, fill="#d4dce4")
        direction = ", ".join(str(camera.get(k)) for k in ("shot_size", "angle", "movement") if camera.get(k))
        draw.text((x + MARGIN, y + 347), direction[:62], font=body_font, fill="#9fcee5")
        intent = str(shot.get("editorial_intent") or "")
        if intent:
            draw.text((x + MARGIN, y + 377), ("IDEA  ·  " + intent)[:58], font=body_font, fill="#f0c778")
        review.append({"shot": i, "prompt": shot["prompt"], "duration": duration,
                       "camera": camera, "editorial_intent": intent,
                       "direction_mode": shot.get("direction_mode", "unspecified"),
                       "hero_frame_connected": has_frame})
    array = np.asarray(sheet, dtype=np.float32).copy() / 255.0
    return torch.from_numpy(array).unsqueeze(0), {"shots": review, "total_duration": sum(int(s.get("duration") or 0) for s in shots)}


class KIEStoryboardContactSheetNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "render"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("contact_sheet", "storyboard_json", "saved_files_json")
    OUTPUT_NODE = True
    DESCRIPTION = "Review up to six planned shots with optional hero frames. Local rendering only; no KIE credits used."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot_sequence_json": ("STRING", {"forceInput": True})},
                "optional": {f"hero_frame_{i}": ("IMAGE",) for i in range(1, 7)}}

    def render(self, shot_sequence_json, **kwargs):
        frames = {i: kwargs[f"hero_frame_{i}"] for i in range(1, 7) if kwargs.get(f"hero_frame_{i}") is not None}
        sheet, metadata = build_storyboard(shot_sequence_json, frames)
        saved = KIEPersistentPreviewImageNode().save_images(sheet, "KIE-Storyboards/Storyboard")
        return {"ui": saved["ui"], "result": (sheet, json.dumps(metadata, ensure_ascii=False), saved["result"][1])}
