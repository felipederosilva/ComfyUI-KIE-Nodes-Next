"""Local, editable shot drafts from an editor's script or brief."""
from __future__ import annotations

import json
import re


NEUTRAL_CAMERA = {
    "shot_size": "medium", "angle": "eye level", "movement": "locked-off",
    "lens": "35mm natural", "speed": "slow", "stabilization": "tripod stable", "focus": "",
}

# Editorial coverage patterns, not provider camera commands. Each entry is a
# beginning / development / detail suggestion distributed across the shot count.
VISUAL_RHYTHMS = {
    "neutral": (),
    "cinematic reveal": (
        ("wide", "eye level", "locked-off", "24mm cinematic wide", "establish the space"),
        ("medium", "low angle", "dolly in", "35mm natural", "move toward the subject"),
        ("close-up", "eye level", "push-in with parallax", "85mm portrait", "land on a telling detail"),
    ),
    "documentary observer": (
        ("wide", "eye level", "handheld follow", "35mm natural", "observe the environment"),
        ("medium", "three-quarter", "steadicam follow", "50mm standard", "stay with the action"),
        ("close-up", "eye level", "locked-off", "85mm portrait", "hold on a human detail"),
    ),
    "product detail": (
        ("medium wide", "three-quarter", "orbit clockwise", "35mm natural", "show form and context"),
        ("medium close-up", "eye level", "dolly in", "50mm standard", "approach a key feature"),
        ("macro detail", "eye level", "locked-off", "100mm macro", "show surface detail"),
    ),
    "action build": (
        ("wide", "eye level", "handheld follow", "24mm cinematic wide", "establish movement"),
        ("medium", "low angle", "truck right", "35mm natural", "increase momentum"),
        ("close-up", "three-quarter", "whip pan", "50mm standard", "finish on the decisive action"),
    ),
    "interview coverage": (
        ("medium", "eye level", "locked-off", "50mm standard", "establish the speaker"),
        ("medium close-up", "three-quarter", "dolly in", "85mm portrait", "draw closer to the speaker"),
        ("close-up", "eye level", "locked-off", "85mm portrait", "hold a clear reaction"),
    ),
}


def _camera_for_rhythm(rhythm: str, index: int, count: int) -> tuple[dict, str]:
    if rhythm not in VISUAL_RHYTHMS:
        raise ValueError("Choose one of the listed visual rhythms.")
    if rhythm == "neutral":
        return dict(NEUTRAL_CAMERA), "Neutral coverage for editorial review."
    pattern = VISUAL_RHYTHMS[rhythm]
    step = 1 if count == 1 else round(index * (len(pattern) - 1) / (count - 1))
    size, angle, movement, lens, intent = pattern[step]
    camera = dict(NEUTRAL_CAMERA)
    camera.update({"shot_size": size, "angle": angle, "movement": movement, "lens": lens})
    if rhythm == "action build":
        camera.update({"speed": "fast", "stabilization": "handheld energetic"})
    elif rhythm == "documentary observer":
        camera.update({"stabilization": "tripod stable" if movement == "locked-off" else
                       "steadicam organic" if movement == "steadicam follow" else "handheld subtle"})
    return camera, intent


def review_shot_plan(value: str) -> tuple[str, int, str]:
    try:
        shots = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Shot plan must be a JSON array. Check commas and quotation marks.") from exc
    if not isinstance(shots, list) or not 1 <= len(shots) <= 6:
        raise ValueError("A shot plan must contain 1 to 6 shots.")
    total = 0
    for index, shot in enumerate(shots, 1):
        if not isinstance(shot, dict) or not isinstance(shot.get("prompt"), str) or not shot["prompt"].strip():
            raise ValueError(f"Shot {index} needs a nonempty prompt.")
        duration = shot.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 15:
            raise ValueError(f"Shot {index} needs an integer duration from 1 to 15 seconds.")
        if "camera" in shot and not isinstance(shot["camera"], dict):
            raise ValueError(f"Shot {index} camera must be a JSON object.")
        total += duration
    summary = f"{len(shots)} shot(s), {total}s total. Review prompts, camera, continuity, and model limits before generation."
    return json.dumps(shots, ensure_ascii=False), total, summary


def _script_segments(text: str, split_mode: str) -> list[str]:
    if split_mode == "one line per shot":
        return [line.strip() for line in text.splitlines() if line.strip()]
    if split_mode == "paragraphs":
        return [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    raise ValueError("Choose paragraphs or one line per shot.")


def _allocate_seconds(segments: list[str], duration: int) -> list[int]:
    if duration < len(segments) or duration > 15 * len(segments):
        raise ValueError(f"Target duration for {len(segments)} shots must be {len(segments)}–{15 * len(segments)} seconds.")
    seconds = [1] * len(segments)
    weights = [max(1, len(segment.split())) for segment in segments]
    for _ in range(duration - len(segments)):
        index = max((i for i, value in enumerate(seconds) if value < 15),
                    key=lambda i: weights[i] / (seconds[i] + 1))
        seconds[index] += 1
    return seconds


def build_shot_draft(text: str, split_mode: str, target_duration: int, max_shots: int,
                     visual_rhythm: str = "neutral") -> tuple[str, int, str]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Write a script or brief before building a shot draft.")
    if len(text) > 30000:
        raise ValueError("Script is too long for one shot draft; split it into scenes.")
    segments = _script_segments(text, split_mode)
    if not 1 <= max_shots <= 6:
        raise ValueError("Maximum shots must be between 1 and 6.")
    if len(segments) > max_shots:
        raise ValueError(f"Found {len(segments)} segments, above the selected {max_shots}-shot limit. Split into separate sequences or combine paragraphs deliberately.")
    lengths = _allocate_seconds(segments, target_duration)
    shots = []
    for index, (segment, length) in enumerate(zip(segments, lengths)):
        camera, intent = _camera_for_rhythm(visual_rhythm, index, len(segments))
        shots.append({"prompt": segment, "duration": length, "camera": camera,
                      "editorial_intent": intent, "direction_mode": "prompt_guidance"})
    proposal, total, _ = review_shot_plan(json.dumps(shots, ensure_ascii=False))
    note = (f"Draft from {len(shots)} source segment(s), {total}s. Text preserved; {visual_rhythm} editorial rhythm. "
            "Camera directions are suggestions that the selected video model may only receive as prompt text. "
            "Copy this JSON to Shot Plan Review's edited_json to refine it before generation.")
    return proposal, total, note


class KIEScriptToShotDraftNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("shot_sequence_json", "total_duration", "review_notes")
    DESCRIPTION = "Turn script paragraphs or lines into a faithful, editable shot proposal. Local only; no KIE credits used."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "script_or_brief": ("STRING", {"default": "", "multiline": True}),
            "split_mode": (["paragraphs", "one line per shot"], {"default": "paragraphs"}),
            "target_duration": ("INT", {"default": 12, "min": 1, "max": 90, "step": 1}),
            "max_shots": ("INT", {"default": 6, "min": 1, "max": 6, "step": 1}),
        }, "optional": {
            "visual_rhythm": (list(VISUAL_RHYTHMS), {"default": "neutral",
                              "tooltip": "Editorial camera suggestion. Existing prompts stay unchanged; model support is checked separately."}),
        }}

    def build(self, script_or_brief, split_mode, target_duration, max_shots, visual_rhythm="neutral"):
        result = build_shot_draft(script_or_brief, split_mode, target_duration, max_shots, visual_rhythm)
        return {"ui": {"kie_shot_plan": [result[0]]}, "result": result}


class KIEShotPlanReviewNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "review"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("shot_sequence_json", "total_duration", "review_notes")
    DESCRIPTION = "Review or override a shot proposal in editable JSON before connecting a storyboard or generation node."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"proposed_json": ("STRING", {"forceInput": True})},
                "optional": {"edited_json": ("STRING", {"default": "", "multiline": True,
                                                "tooltip": "Paste and edit the proposed JSON here. Leave blank to pass the proposal through."})}}

    def review(self, proposed_json, edited_json=""):
        result = review_shot_plan(edited_json.strip() if edited_json.strip() else proposed_json)
        return {"ui": {"kie_shot_plan": [result[0]]}, "result": result}
