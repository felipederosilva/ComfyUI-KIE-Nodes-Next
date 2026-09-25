"""Provider-neutral camera trajectory plan with an inspectable local map."""
from __future__ import annotations

import json
import math

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from .media import KIEPersistentPreviewImageNode


MODES = ("custom path", "dolly", "orbit", "crane")
EASINGS = ("linear", "ease in out", "ease in", "ease out")


def _ease(t: float, mode: str) -> float:
    return {"linear": lambda: t, "ease in out": lambda: t * t * (3 - 2 * t),
            "ease in": lambda: t * t, "ease out": lambda: 1 - (1 - t) ** 2}[mode]()


def build_camera_path(mode: str, duration: float, easing: str, start: tuple[float, float, float],
                      midpoint: tuple[float, float, float], end: tuple[float, float, float],
                      look_at: tuple[float, float, float], orbit_degrees: float = 90.0,
                      samples: int = 9) -> tuple[dict, torch.Tensor, str]:
    if mode not in MODES or easing not in EASINGS:
        raise ValueError("Choose a supported camera path and easing.")
    values = (*start, *midpoint, *end, *look_at, duration, orbit_degrees)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError("Camera coordinates and duration must be finite numbers.")
    if not 0.5 <= duration <= 120 or not 3 <= samples <= 61 or abs(orbit_degrees) > 360:
        raise ValueError("Camera duration, sample count, or orbit angle is outside the supported range.")
    frames = []
    for index in range(samples):
        u = _ease(index / (samples - 1), easing)
        if mode == "orbit":
            dx, dz = start[0] - look_at[0], start[2] - look_at[2]
            angle = math.radians(orbit_degrees * u)
            position = (look_at[0] + dx * math.cos(angle) - dz * math.sin(angle),
                        start[1] + (end[1] - start[1]) * u,
                        look_at[2] + dx * math.sin(angle) + dz * math.cos(angle))
        elif mode == "crane":
            position = (start[0] + (end[0] - start[0]) * u,
                        start[1] + (end[1] - start[1]) * u,
                        start[2] + (end[2] - start[2]) * u)
        elif mode == "dolly":
            position = tuple(start[k] + (end[k] - start[k]) * u for k in range(3))
        else:
            position = tuple((1 - u) ** 2 * start[k] + 2 * (1 - u) * u * midpoint[k] + u ** 2 * end[k]
                             for k in range(3))
        frames.append({"time_seconds": round(duration * index / (samples - 1), 3),
                       "position": [round(v, 4) for v in position], "look_at": list(look_at)})
    plan = {"schema_version": 1, "mode": mode, "duration_seconds": duration, "easing": easing,
            "keyframes": frames, "application": "prompt_guidance_unless_model_adapter_documents_native_fields"}
    direction = (f"Camera path: {mode}, {duration:g}s, {easing}; start at {frames[0]['position']}, "
                 f"end at {frames[-1]['position']}, keep attention on {list(look_at)}. "
                 "Treat these coordinates as editorial intent unless the selected model documents native camera controls.")
    image = _path_preview(frames, look_at)
    return plan, image, direction


def _path_preview(frames: list[dict], look_at: tuple[float, float, float]) -> torch.Tensor:
    canvas = Image.new("RGB", (640, 460), "#17202a")
    draw = ImageDraw.Draw(canvas)
    positions = [(frame["position"][0], frame["position"][2]) for frame in frames]
    points = [*positions, (look_at[0], look_at[2])]
    xs, zs = [p[0] for p in points], [p[1] for p in points]
    span = max(max(xs) - min(xs), max(zs) - min(zs), 1.0)
    center_x, center_z = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    scale = 330 / span

    def xy(x, z):
        return (int(320 + (x - center_x) * scale), int(220 + (z - center_z) * scale))

    draw.line([xy(*p) for p in positions], fill="#57c5eb", width=5)
    for index, frame in enumerate(frames):
        px, py = xy(*positions[index])
        radius = 8 if index in (0, len(frames) - 1) else 4
        color = "#6ee7b7" if index == 0 else "#ffc773" if index == len(frames) - 1 else "#b7dded"
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
    tx, ty = xy(look_at[0], look_at[2])
    draw.ellipse((tx - 7, ty - 7, tx + 7, ty + 7), outline="#f787a9", width=3)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 12), "TOP VIEW · camera path", font=font, fill="#f0f4f7")
    draw.text((16, 432), "GREEN start   AMBER end   PINK look-at   height shown in JSON keyframes", font=font, fill="#d5dfe8")
    return torch.from_numpy(np.asarray(canvas, dtype=np.float32).copy() / 255.0).unsqueeze(0)


class KIECameraPathNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "plan"
    RETURN_TYPES = ("STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("camera_direction", "camera_path_json", "top_view")
    OUTPUT_NODE = True
    DESCRIPTION = "Plan a keyframed 3D camera path and inspect its top view. Coordinates are editorial intent, not universal physical camera control."

    @classmethod
    def INPUT_TYPES(cls):
        coordinate = lambda default: ("FLOAT", {"default": default, "min": -1000, "max": 1000, "step": 0.1})
        return {"required": {
            "path_mode": (list(MODES), {"default": "dolly"}),
            "duration_seconds": ("FLOAT", {"default": 5.0, "min": 0.5, "max": 120, "step": 0.5}),
            "easing": (list(EASINGS), {"default": "ease in out"}),
            "start_x": coordinate(0.0), "start_y": coordinate(1.6), "start_z": coordinate(-4.0),
            "end_x": coordinate(0.0), "end_y": coordinate(1.6), "end_z": coordinate(-2.0),
            "look_at_x": coordinate(0.0), "look_at_y": coordinate(1.6), "look_at_z": coordinate(0.0),
        }, "optional": {
            "mid_x": coordinate(1.0), "mid_y": coordinate(1.6), "mid_z": coordinate(-3.0),
            "orbit_degrees": ("FLOAT", {"default": 90.0, "min": -360, "max": 360, "step": 5}),
            "keyframe_samples": ("INT", {"default": 9, "min": 3, "max": 61}),
        }}

    def plan(self, path_mode, duration_seconds, easing, start_x, start_y, start_z,
             end_x, end_y, end_z, look_at_x, look_at_y, look_at_z,
             mid_x=1.0, mid_y=1.6, mid_z=-3.0, orbit_degrees=90.0, keyframe_samples=9):
        data, image, direction = build_camera_path(
            path_mode, duration_seconds, easing, (start_x, start_y, start_z),
            (mid_x, mid_y, mid_z), (end_x, end_y, end_z),
            (look_at_x, look_at_y, look_at_z), orbit_degrees, keyframe_samples)
        saved = KIEPersistentPreviewImageNode().save_images(image, "KIE-Camera/Path")
        return {"ui": saved["ui"], "result": (direction, json.dumps(data, ensure_ascii=False), image)}
