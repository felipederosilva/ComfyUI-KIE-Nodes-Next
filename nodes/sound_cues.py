"""Reviewable sound-design cue sheet; no fabricated sound recognition or paid calls."""
from __future__ import annotations

import json

from .video_events import _editor_cues, _read_timeline


def sound_cue_sheet(events_json: str, editor_cues_json: str, ambience: str,
                    dialogue_priority: bool = True) -> tuple[str, str]:
    timeline = _read_timeline(events_json)
    duration = float(timeline["duration_seconds"])
    editor_cues = _editor_cues(editor_cues_json, duration)
    if not editor_cues:
        editor_cues = [{"time_seconds": e["time_seconds"], "description": e["description"]}
                       for e in timeline["events"] if e.get("type") == "editor_verified_event"
                       and isinstance(e.get("description"), str)]
    bed = str(ambience or "").strip()
    if not bed:
        raise ValueError("Describe the desired ambience; silence is also a valid description.")
    if len(bed) > 1500:
        raise ValueError("Ambience description exceeds 1,500 characters.")
    cues = []
    for index, cue in enumerate(editor_cues, 1):
        cues.append({"id": f"SFX-{index:02d}", "time_seconds": cue["time_seconds"],
                     "description": cue["description"], "status": "editor-verified",
                     "action": "source or generate a matching effect, then align in the editor"})
    unverified = [
        {"time_seconds": marker["time_seconds"], "reason": marker["type"]}
        for marker in timeline["events"] if marker.get("type") in
        {"visual_cut_candidate", "visual_activity"}
    ][:30]
    sheet = {"schema_version": 1, "duration_seconds": duration, "ambience": bed,
             "dialogue_priority": bool(dialogue_priority), "cues": cues,
             "visual_markers_to_review": unverified,
             "policy": "Visual changes are not interpreted as sounds or actions. Only editor-described cues enter the SFX list."}
    brief = (f"Sound design for a {duration:g}-second video. Continuous ambience: {bed}. "
             f"{'Keep dialogue clear; duck ambience and effects underneath speech. ' if dialogue_priority else ''}"
             "Keep effects isolated from the music bed for independent mixing. "
             + ("Editor-approved timed effects: " + "; ".join(
                 f"{cue['time_seconds']:g}s {cue['description']}" for cue in cues)
                if cues else "No timed effects are approved yet; review visual markers before adding them."))
    return json.dumps(sheet, ensure_ascii=False), brief


class KIESoundCueSheetNode:
    CATEGORY = "KIE Next/Studio/Audio"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("sound_cues_json", "sound_design_brief")
    DESCRIPTION = "Turn editor-described events into a timed SFX/ambience brief. Pixel changes alone never become claimed sound events. No generation is submitted."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"events_json": ("STRING", {"forceInput": True}),
                             "ambience": ("STRING", {"default": "quiet interior room tone", "multiline": True}),
                             "dialogue_priority": ("BOOLEAN", {"default": True})},
                "optional": {"editor_cues_json": ("STRING", {"default": "", "multiline": True,
                                                    "tooltip": "Approved cues: [{\"time_seconds\": 4, \"description\": \"door closes\"}]."})}}

    def build(self, events_json, ambience, dialogue_priority=True, editor_cues_json=""):
        return sound_cue_sheet(events_json, editor_cues_json, ambience, dialogue_priority)
