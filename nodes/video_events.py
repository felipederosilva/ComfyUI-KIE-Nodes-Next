"""Local visual timeline analysis and editable, event-based music briefs."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from ..kie.media import _comfy_temp_dir, video_to_temp_file


def analyze_video_file(path: str, *, sample_interval: float = 0.5, max_seconds: int = 300,
                       cut_threshold: float = 0.30, activity_threshold: float = 0.07) -> dict:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Video event analysis needs OpenCV in ComfyUI's Python environment.") from exc
    if not 0.2 <= sample_interval <= 5 or not 1 <= max_seconds <= 3600:
        raise ValueError("Choose a sample interval of 0.2–5 seconds and a maximum length of 1–3600 seconds.")
    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise ValueError("Could not decode the connected video for local analysis.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(frames) or frames <= 0:
            raise ValueError("Video frame rate or duration is unavailable.")
        duration = frames / fps
        limit = min(duration, float(max_seconds))
        events = [{"time_seconds": 0.0, "type": "start", "visual_change": 0.0}]
        previous = None
        last_activity = -10.0
        samples = 0
        t = 0.0
        while t < limit:
            capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = capture.read()
            if not ok:
                break
            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            samples += 1
            if previous is not None:
                difference = float(np.mean(cv2.absdiff(gray, previous))) / 255.0
                if difference >= cut_threshold:
                    events.append({"time_seconds": round(t, 2), "type": "visual_cut_candidate",
                                   "visual_change": round(difference, 3)})
                    last_activity = t
                elif difference >= activity_threshold and t - last_activity >= 2.0:
                    events.append({"time_seconds": round(t, 2), "type": "visual_activity",
                                   "visual_change": round(difference, 3)})
                    last_activity = t
            previous = gray
            t += sample_interval
        if samples == 0:
            raise ValueError("No decodable video frames were found.")
        return {"schema_version": 1, "duration_seconds": round(duration, 2),
                "analyzed_seconds": round(min(t, limit), 2), "sample_interval_seconds": sample_interval,
                "events": events[:200], "truncated": duration > max_seconds or len(events) > 200,
                "interpretation": "Pixel-change markers only. Confirm cuts and describe story events manually; camera movement can resemble a cut."}
    finally:
        capture.release()


def _read_timeline(value: str) -> dict:
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Connect Video Event Analysis JSON.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("Timeline needs an events array.")
    duration = data.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0 < duration <= 86400:
        raise ValueError("Timeline duration is missing or invalid.")
    for index, event in enumerate(data["events"], 1):
        if not isinstance(event, dict):
            raise ValueError(f"Timeline event {index} must be an object.")
        moment = event.get("time_seconds")
        if (isinstance(moment, bool) or not isinstance(moment, (int, float)) or
                not math.isfinite(moment) or not 0 <= moment <= duration):
            raise ValueError(f"Timeline event {index} needs a time within the video.")
    return data


def _editor_cues(value: str, duration: float) -> list[dict]:
    if not str(value or "").strip():
        return []
    try:
        cues = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("editor_cues_json must be a JSON array.") from exc
    if not isinstance(cues, list) or len(cues) > 30:
        raise ValueError("Provide at most 30 editor cues in a JSON array.")
    normalized = []
    for index, cue in enumerate(cues, 1):
        if not isinstance(cue, dict):
            raise ValueError(f"Editor cue {index} must be an object.")
        time = cue.get("time_seconds")
        description = cue.get("description")
        if (isinstance(time, bool) or not isinstance(time, (int, float)) or
                not math.isfinite(time) or not 0 <= time <= duration or
                not isinstance(description, str) or not description.strip()):
            raise ValueError(f"Editor cue {index} needs a time within the video and a description.")
        normalized.append({"time_seconds": round(float(time), 2), "description": description.strip()[:250]})
    return sorted(normalized, key=lambda item: item["time_seconds"])


def music_brief(timeline_json: str, mood: str, style: str, tempo_bpm: int,
                editor_cues_json: str = "") -> tuple[str, str, str]:
    timeline = _read_timeline(timeline_json)
    duration = float(timeline["duration_seconds"])
    cues = _editor_cues(editor_cues_json, duration)
    source = "editor annotations" if cues else "visual-change suggestions"
    reviewed = [{"time_seconds": e["time_seconds"], "description": e["description"]}
                for e in timeline["events"] if e.get("type") == "editor_verified_event"
                and isinstance(e.get("description"), str)]
    if not cues:
        cues = reviewed
        if reviewed:
            source = "editor-reviewed vision notes"
    if not str(mood or "").strip() or not str(style or "").strip() or not 40 <= tempo_bpm <= 240:
        raise ValueError("Set a mood, music style, and tempo between 40 and 240 BPM.")
    visual = [e for e in timeline["events"] if isinstance(e, dict) and e.get("type") in
              {"visual_cut_candidate", "visual_activity"}]
    moments = [{"time_seconds": cue["time_seconds"], "source": "editor", "description": cue["description"]}
               for cue in cues]
    if not cues:
        moments.extend({"time_seconds": e["time_seconds"], "source": "visual_analysis",
                        "description": "possible scene transition" if e["type"] == "visual_cut_candidate" else "visual activity rises"}
                       for e in visual[:12])
    moments.sort(key=lambda event: event["time_seconds"])
    timeline_text = "; ".join(f"{m['time_seconds']:g}s: {m['description']}" for m in moments[:12])
    prompt = (f"Instrumental background score for a {duration:g}-second video. "
              f"Mood: {mood.strip()}. Musical style: {style.strip()}. Approximate tempo: {tempo_bpm} BPM. "
              "No vocals. Leave space for dialogue and key sound effects. "
              f"Shape the arrangement around these reviewable picture moments: {timeline_text or 'maintain a coherent arc'}. "
              "Begin and end cleanly for editing; final timing will be fitted in the video editor.")
    return prompt, str(style).strip(), json.dumps({"duration_seconds": duration, "cues": moments,
                    "instrumental": True, "source": source}, ensure_ascii=False)


class KIEVideoEventAnalysisNode:
    CATEGORY = "KIE Next/Studio/Video Analysis"
    FUNCTION = "analyze"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("events_json", "analysis_summary")
    DESCRIPTION = "Detect timecoded visual changes locally. It cannot identify actions or meaning; confirm markers before music or SFX work."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("VIDEO",),
                             "sample_interval_seconds": ("FLOAT", {"default": 0.5, "min": 0.2, "max": 5.0, "step": 0.1}),
                             "max_seconds": ("INT", {"default": 300, "min": 1, "max": 3600})}}

    def analyze(self, video, sample_interval_seconds=0.5, max_seconds=300):
        created = not isinstance(video, str)
        path = video_to_temp_file(video)
        try:
            data = analyze_video_file(path, sample_interval=float(sample_interval_seconds), max_seconds=int(max_seconds))
        finally:
            location = Path(path)
            if created and location.parent.resolve() == Path(_comfy_temp_dir()).resolve() and location.name.startswith("kie_upload_"):
                location.unlink(missing_ok=True)
        return json.dumps(data, ensure_ascii=False), (
            f"Analyzed {data['analyzed_seconds']:g}s of {data['duration_seconds']:g}s; "
            f"{len(data['events']) - 1} possible visual changes. Confirm event meaning manually.")


class KIEMusicBriefNode:
    CATEGORY = "KIE Next/Studio/Audio"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN", "BOOLEAN", "STRING")
    RETURN_NAMES = ("music_prompt", "music_style", "suno_custom_mode", "instrumental", "cue_sheet_json")
    DESCRIPTION = "Build an editable instrumental music brief from video timing and optional editor-verified story cues. Connect to a supported music model manually."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"events_json": ("STRING", {"forceInput": True}),
                             "mood": ("STRING", {"default": "hopeful, restrained"}),
                             "music_style": ("STRING", {"default": "cinematic ambient"}),
                             "tempo_bpm": ("INT", {"default": 90, "min": 40, "max": 240})},
                "optional": {"editor_cues_json": ("STRING", {"default": "", "multiline": True,
                                                    "tooltip": "Optional [{\"time_seconds\": 4, \"description\": \"character sees the letter\"}]"})}}

    def build(self, events_json, mood, music_style, tempo_bpm, editor_cues_json=""):
        prompt, style, sheet = music_brief(events_json, mood, music_style, tempo_bpm, editor_cues_json)
        return (prompt, style, False, True, sheet)
