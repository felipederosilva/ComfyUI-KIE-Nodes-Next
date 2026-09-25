"""Adapt a reviewed sound cue to the documented KIE Suno Sounds prompt fields."""
from __future__ import annotations

import json


def sfx_prompt(sheet_json: str, mode: str, cue_number: int) -> tuple[str, bool, bool, float, str]:
    try:
        data = json.loads(sheet_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Connect a Sound Cue Sheet JSON output.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cues"), list):
        raise ValueError("Sound Cue Sheet is missing the cues list.")
    if mode == "ambient loop":
        ambience = str(data.get("ambience") or "").strip()
        if not ambience:
            raise ValueError("Sound Cue Sheet has no ambience description.")
        prompt = f"Seamless environmental ambience loop: {ambience}. No music, no speech, no melody. Consistent sound bed with a clean loop point."
        return prompt[:500], True, False, 0.0, "AMBIENCE"
    if mode != "timed effect":
        raise ValueError("Choose timed effect or ambient loop.")
    cues = data["cues"]
    if not 1 <= cue_number <= len(cues):
        raise ValueError(f"Cue number {cue_number} is unavailable; the sheet contains {len(cues)} approved timed effect(s).")
    cue = cues[cue_number - 1]
    if not isinstance(cue, dict) or cue.get("status") != "editor-verified":
        raise ValueError("Only editor-verified cues can become timed SFX prompts.")
    description = str(cue.get("description") or "").strip()
    if not description:
        raise ValueError("Selected cue has no description.")
    prompt = f"Isolated cinematic sound effect: {description}. No music, no speech, no melody. Distinct attack and natural decay; clean background for editorial placement."
    return prompt[:500], False, False, float(cue["time_seconds"]), str(cue.get("id") or f"SFX-{cue_number:02d}")


class KIESFXPromptNode:
    CATEGORY = "KIE Next/Studio/Audio"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "BOOLEAN", "BOOLEAN", "FLOAT", "STRING")
    RETURN_NAMES = ("suno_sounds_prompt", "sound_loop", "grab_lyrics", "cue_time_seconds", "cue_id")
    DESCRIPTION = "Select one approved timed effect or ambient loop for KIE's Suno Sounds node. Review before connecting to paid generation."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"sound_cues_json": ("STRING", {"forceInput": True}),
                             "mode": (["timed effect", "ambient loop"], {"default": "timed effect"}),
                             "cue_number": ("INT", {"default": 1, "min": 1, "max": 30})}}

    def build(self, sound_cues_json, mode="timed effect", cue_number=1):
        return sfx_prompt(sound_cues_json, mode, int(cue_number))
