"""Local frame sampling and human-gated import of visual-model event notes."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from ..kie.media import _comfy_temp_dir, video_to_temp_file
from .video_events import _read_timeline


def sample_video_file(path: str, frame_count: int = 8, max_seconds: int = 300) -> tuple[torch.Tensor, str]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Video frame sampling needs OpenCV in ComfyUI's Python environment.") from exc
    if not 2 <= frame_count <= 12 or not 1 <= max_seconds <= 3600:
        raise ValueError("Choose 2–12 frames and a 1–3600 second analysis limit.")
    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise ValueError("Could not decode connected video.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(total) or total <= 0:
            raise ValueError("Source video has no usable frame timing.")
        duration = total / fps
        limit = min(duration, float(max_seconds))
        # Avoid seeking to the exact EOF; some decoders return no frame there.
        times = np.linspace(0, max(0, limit - 1 / fps), frame_count)
        frames = []
        for moment in times:
            capture.set(cv2.CAP_PROP_POS_MSEC, float(moment) * 1000)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"Could not decode a sample frame at {moment:.2f}s.")
            rgb = cv2.cvtColor(cv2.resize(frame, (512, 288), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            frames.append(torch.from_numpy(rgb.astype(np.float32) / 255.0))
        record = {"schema_version": 1, "duration_seconds": round(duration, 3),
                  "sampled_seconds": [round(float(t), 3) for t in times],
                  "note": "Sparse still frames omit motion/audio between samples. A vision model's description requires editor verification."}
        return torch.stack(frames), json.dumps(record, ensure_ascii=False)
    finally:
        capture.release()


def frame_contact_sheet(frames: torch.Tensor, times_json: str) -> torch.Tensor:
    record = json.loads(times_json)
    times = record.get("sampled_seconds") or []
    if len(times) != frames.shape[0]:
        raise ValueError("Frame count and timestamps differ.")
    columns = 2
    rows = math.ceil(frames.shape[0] / columns)
    tile_width, tile_height = 512, 315
    canvas = Image.new("RGB", (tile_width * columns, tile_height * rows), "#17202a")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for index, (tensor, moment) in enumerate(zip(frames, times)):
        x, y = (index % columns) * tile_width, (index // columns) * tile_height
        array = (tensor.clamp(0, 1).numpy() * 255).round().astype(np.uint8)
        canvas.paste(Image.fromarray(array, "RGB"), (x, y + 27))
        draw.text((x + 8, y + 4), f"FRAME {index + 1} · {float(moment):.2f}s", font=font, fill="#f2cf81")
    return torch.from_numpy(np.asarray(canvas, dtype=np.float32).copy() / 255.0).unsqueeze(0)


def reviewed_event_timeline(frame_times_json: str, model_events_json: str,
                            reviewed: bool) -> str:
    if not reviewed:
        raise ValueError("Inspect the video and model descriptions, correct any mistakes, then enable editor_reviewed.")
    try:
        times = json.loads(frame_times_json)
        data = json.loads(model_events_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Provide valid frame-times and reviewed model-events JSON.") from exc
    duration = times.get("duration_seconds") if isinstance(times, dict) else None
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Frame timing record is invalid.")
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list) or not 1 <= len(events) <= 30:
        raise ValueError("Reviewed events JSON needs 1–30 events.")
    checked = []
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ValueError(f"Event {index} must be an object.")
        moment, description = event.get("time_seconds"), event.get("description")
        if (isinstance(moment, bool) or not isinstance(moment, (int, float)) or
                not math.isfinite(moment) or not 0 <= moment <= duration or
                not isinstance(description, str) or not description.strip() or len(description) > 250):
            raise ValueError(f"Event {index} needs a valid time and a description of at most 250 characters.")
        checked.append({"time_seconds": round(float(moment), 2), "type": "editor_verified_event",
                        "description": description.strip(), "source": "editor-reviewed vision notes"})
    timeline = {"schema_version": 1, "duration_seconds": duration,
                "events": [{"time_seconds": 0.0, "type": "start"}, *sorted(checked, key=lambda item: item["time_seconds"])],
                "interpretation": "Editor-reviewed still-frame notes, not an automatically verified audiovisual transcript."}
    _read_timeline(json.dumps(timeline))
    return json.dumps(timeline, ensure_ascii=False)


class KIEVideoFrameSamplerNode:
    CATEGORY = "KIE Next/Studio/Video Analysis"
    FUNCTION = "sample"
    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("ordered_frames", "labelled_contact_sheet", "frame_times_json", "vision_review_prompt")
    DESCRIPTION = "Sample ordered still frames locally for an explicitly connected vision model. Frames omit motion/audio; review its descriptions against the video."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("VIDEO",),
                             "frame_count": ("INT", {"default": 8, "min": 2, "max": 12}),
                             "max_seconds": ("INT", {"default": 300, "min": 1, "max": 3600})}}

    def sample(self, video, frame_count=8, max_seconds=300):
        created = not isinstance(video, str)
        path = video_to_temp_file(video)
        try:
            frames, record = sample_video_file(path, int(frame_count), int(max_seconds))
        finally:
            location = Path(path)
            if created and location.parent.resolve() == Path(_comfy_temp_dir()).resolve() and location.name.startswith("kie_upload_"):
                location.unlink(missing_ok=True)
        prompt = ("These are ordered, sparse frames from one video. Use the connected frame_times_json to map order to time. "
                  "Describe only visible events; do not invent speech, sound, actions between frames, or certainty about intent. "
                  "Return JSON only: {\"events\":[{\"time_seconds\":0.0,\"description\":\"visible event\"}]}. "
                  "The editor will verify every description against the full video before sound or music generation. "
                  f"frame_times_json: {record}")
        return frames, frame_contact_sheet(frames, record), record, prompt


class KIEReviewedEventsNode:
    CATEGORY = "KIE Next/Studio/Video Analysis"
    FUNCTION = "review"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("reviewed_events_json",)
    DESCRIPTION = "Convert corrected vision-model JSON to timed editor-verified events. Requires explicit review confirmation; no provider call."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"frame_times_json": ("STRING", {"forceInput": True}),
                             "corrected_events_json": ("STRING", {"default": '{"events":[]}', "multiline": True}),
                             "editor_reviewed": ("BOOLEAN", {"default": False})}}

    def review(self, frame_times_json, corrected_events_json, editor_reviewed=False):
        return (reviewed_event_timeline(frame_times_json, corrected_events_json, bool(editor_reviewed)),)
