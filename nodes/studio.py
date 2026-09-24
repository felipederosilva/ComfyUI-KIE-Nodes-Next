from __future__ import annotations

import json
from typing import Any

from ..kie.client import KIEAPIError
from ..kie.helpers import make_client
from ..kie.media import upload_audio, upload_image_batch, video_to_temp_file
from .generated import _credit_balance, _result_for_kind


CAMERA_MOVES = [
    "locked-off", "pan left", "pan right", "tilt up", "tilt down",
    "dolly in", "dolly out", "truck left", "truck right", "pedestal up",
    "pedestal down", "orbit clockwise", "orbit counter-clockwise",
    "crane up", "crane down", "handheld follow", "steadicam follow",
    "drone flyover", "push-in with parallax", "pull-back reveal", "whip pan",
]
SHOT_SIZES = [
    "extreme wide", "wide", "full body", "medium wide", "medium",
    "medium close-up", "close-up", "extreme close-up", "macro detail",
]
ANGLES = [
    "eye level", "low angle", "high angle", "bird's-eye", "worm's-eye",
    "Dutch angle", "over-the-shoulder", "POV", "profile", "three-quarter",
]
LENSES = [
    "14mm ultra-wide", "18mm wide", "24mm cinematic wide", "35mm natural",
    "50mm standard", "85mm portrait", "100mm macro", "135mm telephoto",
    "anamorphic", "fisheye", "tilt-shift",
]
MOTION_SPEEDS = ["very slow", "slow", "moderate", "fast", "very fast", "speed ramp"]
STABILIZATION = ["tripod stable", "gimbal smooth", "steadicam organic", "handheld subtle", "handheld energetic"]


def _camera_sentence(shot_size: str, angle: str, movement: str, lens: str, speed: str, stabilization: str, focus: str) -> str:
    parts = [
        f"{shot_size} shot", f"{angle} camera", f"{movement} movement",
        f"captured with a {lens} lens", f"{speed} motion", stabilization,
    ]
    if focus.strip():
        parts.append(f"focus behavior: {focus.strip()}")
    return "Cinematography: " + ", ".join(parts) + "."


def _parse_shots(value: str) -> list[dict[str, Any]]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        shots = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"shot_sequence_json must contain valid JSON: {exc}") from exc
    if not isinstance(shots, list):
        raise ValueError("shot_sequence_json must be a JSON array.")
    normalized = []
    for index, shot in enumerate(shots[:6], 1):
        if not isinstance(shot, dict) or not str(shot.get("prompt") or "").strip():
            raise ValueError(f"Shot {index} needs a prompt.")
        duration = int(shot.get("duration") or 1)
        if duration < 1 or duration > 15:
            raise ValueError(f"Shot {index} duration must be between 1 and 15 seconds.")
        normalized.append({"prompt": str(shot["prompt"]).strip(), "duration": duration})
    return normalized


class KIECameraDirectorNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("camera_direction", "camera_plan_json")
    DESCRIPTION = "Build reusable cinematic camera language for KIE video nodes."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "shot_size": (SHOT_SIZES, {"default": "medium"}),
            "camera_angle": (ANGLES, {"default": "eye level"}),
            "camera_movement": (CAMERA_MOVES, {"default": "dolly in"}),
            "lens": (LENSES, {"default": "35mm natural"}),
            "motion_speed": (MOTION_SPEEDS, {"default": "slow"}),
            "stabilization": (STABILIZATION, {"default": "gimbal smooth"}),
        }, "optional": {
            "focus_behavior": ("STRING", {"default": "shallow depth of field, smooth rack focus to the subject", "multiline": True}),
        }}

    def build(self, shot_size, camera_angle, camera_movement, lens, motion_speed, stabilization, focus_behavior=""):
        plan = {
            "shot_size": shot_size, "camera_angle": camera_angle,
            "camera_movement": camera_movement, "lens": lens,
            "motion_speed": motion_speed, "stabilization": stabilization,
            "focus_behavior": focus_behavior,
        }
        return (_camera_sentence(shot_size, camera_angle, camera_movement, lens, motion_speed, stabilization, focus_behavior), json.dumps(plan, ensure_ascii=False, indent=2))


class KIEShotSequenceNode:
    CATEGORY = "KIE Next/Studio/Direction"
    FUNCTION = "build"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("shot_sequence_json", "total_duration", "director_prompt")
    DESCRIPTION = "Create a Kling-compatible sequence of up to six directed shots."

    @classmethod
    def INPUT_TYPES(cls):
        required = {}
        optional = {}
        for i in range(1, 7):
            target = required if i == 1 else optional
            target[f"shot_{i}_prompt"] = ("STRING", {"default": "" if i > 1 else "Establish the subject and environment", "multiline": True})
            target[f"shot_{i}_duration"] = ("INT", {"default": 2, "min": 1, "max": 15, "step": 1})
        return {"required": required, "optional": optional}

    def build(self, **kwargs):
        shots = []
        for i in range(1, 7):
            prompt = str(kwargs.get(f"shot_{i}_prompt") or "").strip()
            if prompt:
                shots.append({"prompt": prompt, "duration": int(kwargs.get(f"shot_{i}_duration") or 1)})
        total = sum(s["duration"] for s in shots)
        director = " | ".join(f"Shot {i}: {s['prompt']} ({s['duration']}s)" for i, s in enumerate(shots, 1))
        return (json.dumps(shots, ensure_ascii=False), total, director)


class KIEKlingOmniStudioNode:
    CATEGORY = "KIE Next/Studio/Kling"
    FUNCTION = "execute"
    RETURN_TYPES = ("VIDEO", "STRING", "STRING", "STRING", "STRING", "FLOAT", "FLOAT")
    RETURN_NAMES = ("video", "url", "all_urls_json", "task_id", "raw_json", "credits_consumed", "credits_left")
    DESCRIPTION = "Purpose-built Kling 3.0 Omni director with single, automatic, or manually planned multi-shot generation."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"default": "", "multiline": True}),
            "shot_mode": (["single shot", "automatic multi-shot", "manual shot sequence"], {"default": "single shot"}),
            "resolution": (["720p", "1080p", "4k"], {"default": "720p"}),
            "aspect_ratio": (["16:9", "9:16", "1:1"], {"default": "16:9"}),
            "duration": ("INT", {"default": 5, "min": 3, "max": 15, "step": 1}),
            "audio": ("BOOLEAN", {"default": False}),
        }, "optional": {
            "camera_direction": ("STRING", {"default": "", "multiline": True}),
            "shot_sequence_json": ("STRING", {"default": "[]", "multiline": True}),
            "first_frame": ("IMAGE",),
            "timeout_seconds": ("INT", {"default": 1200, "min": 30, "max": 7200, "step": 30}),
        }}

    def execute(self, prompt, shot_mode, resolution, aspect_ratio, duration, audio, camera_direction="", shot_sequence_json="[]", first_frame=None, timeout_seconds=1200):
        client = make_client(None)
        credits_before = _credit_balance(client)
        combined = str(prompt).strip()
        if str(camera_direction).strip():
            combined = f"{combined}\n\n{str(camera_direction).strip()}".strip()
        if not combined:
            raise ValueError("Kling Studio requires a prompt or camera direction.")
        payload: dict[str, Any] = {
            "prompt": combined, "audio": bool(audio), "resolution": resolution,
            "aspect_ratio": aspect_ratio, "duration": int(duration),
        }
        if shot_mode == "manual shot sequence":
            shots = _parse_shots(shot_sequence_json)
            if not shots:
                raise ValueError("Manual shot sequence mode requires at least one shot.")
            if sum(s["duration"] for s in shots) != int(duration):
                raise ValueError("The sum of shot durations must equal the total duration.")
            payload.update({"customize_multi_shots": True, "prefer_multi_shots": False, "multi_prompt": shots})
        elif shot_mode == "automatic multi-shot":
            payload.update({"customize_multi_shots": False, "prefer_multi_shots": True})
        else:
            payload.update({"customize_multi_shots": False, "prefer_multi_shots": False})
        model = "kling-3.0-omni/text-to-video"
        if first_frame is not None:
            payload["image_urls"] = upload_image_batch(client, first_frame, prefix="kling_omni_frame")
            model = "kling-3.0-omni/image-to-video"
        task_id = client.create_task(model, payload)
        result = client.wait_for_task(task_id, timeout_seconds=int(timeout_seconds))
        return _result_for_kind(client, "video", result.raw, task_id, result.credits_consumed, credits_before)


class KIESeedanceStudioNode:
    CATEGORY = "KIE Next/Studio/ByteDance"
    FUNCTION = "execute"
    RETURN_TYPES = ("VIDEO", "STRING", "STRING", "STRING", "STRING", "FLOAT", "FLOAT")
    RETURN_NAMES = ("video", "url", "all_urls_json", "task_id", "raw_json", "credits_consumed", "credits_left")
    DESCRIPTION = "Mode-aware Seedance director with frames, multimodal references, camera language, audio, and last-frame output control."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": (["bytedance/seedance-2", "bytedance/seedance-2-fast", "bytedance/seedance-2-mini", "bytedance/seedance-2-5"], {"default": "bytedance/seedance-2-5"}),
            "generation_mode": (["text", "first frame", "first + last frame", "multimodal reference"], {"default": "text"}),
            "prompt": ("STRING", {"default": "", "multiline": True}),
            "resolution": (["480p", "720p", "1080p", "4k"], {"default": "720p"}),
            "aspect_ratio": (["adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"], {"default": "adaptive"}),
            "duration": ("INT", {"default": 5, "min": -1, "max": 30, "step": 1}),
            "generate_audio": ("BOOLEAN", {"default": True}),
        }, "optional": {
            "camera_direction": ("STRING", {"default": "", "multiline": True}),
            "first_frame": ("IMAGE",), "last_frame": ("IMAGE",),
            "reference_image_1": ("IMAGE",), "reference_image_2": ("IMAGE",), "reference_image_3": ("IMAGE",),
            "reference_video": ("VIDEO",), "reference_audio": ("AUDIO",),
            "return_last_frame": ("BOOLEAN", {"default": False}),
            "web_search": ("BOOLEAN", {"default": False}),
            "timeout_seconds": ("INT", {"default": 1200, "min": 30, "max": 7200, "step": 30}),
        }}

    def execute(self, model, generation_mode, prompt, resolution, aspect_ratio, duration, generate_audio, camera_direction="", first_frame=None, last_frame=None, reference_image_1=None, reference_image_2=None, reference_image_3=None, reference_video=None, reference_audio=None, return_last_frame=False, web_search=False, timeout_seconds=1200):
        client = make_client(None)
        credits_before = _credit_balance(client)
        combined = str(prompt).strip()
        if str(camera_direction).strip():
            combined = f"{combined}\n\n{str(camera_direction).strip()}".strip()
        if not combined:
            raise ValueError("Seedance Studio requires a prompt or camera direction.")
        payload: dict[str, Any] = {
            "prompt": combined, "resolution": resolution, "aspect_ratio": aspect_ratio,
            "duration": int(duration), "generate_audio": bool(generate_audio),
            "return_last_frame": bool(return_last_frame), "web_search": bool(web_search),
        }
        if generation_mode in {"first frame", "first + last frame"}:
            if first_frame is None:
                raise ValueError("This Seedance mode requires a first frame.")
            payload["first_frame_url"] = upload_image_batch(client, first_frame, prefix="seedance_first")[0]
            if generation_mode == "first + last frame":
                if last_frame is None:
                    raise ValueError("First + last frame mode requires a last frame.")
                payload["last_frame_url"] = upload_image_batch(client, last_frame, prefix="seedance_last")[0]
        elif generation_mode == "multimodal reference":
            refs = []
            for index, image in enumerate((reference_image_1, reference_image_2, reference_image_3), 1):
                if image is not None:
                    refs.extend(upload_image_batch(client, image, prefix=f"seedance_ref_{index}"))
            if refs:
                payload["reference_image_urls"] = refs
            if reference_video is not None:
                payload["reference_video_urls"] = [client.upload_file(video_to_temp_file(reference_video), upload_path="comfyui/videos")]
            if reference_audio is not None:
                payload["reference_audio_urls"] = [upload_audio(client, reference_audio, prefix="seedance_ref")]
            if not any(k in payload for k in ("reference_image_urls", "reference_video_urls", "reference_audio_urls")):
                raise ValueError("Multimodal reference mode requires at least one image, video, or audio reference.")
        task_id = client.create_task(model, payload)
        result = client.wait_for_task(task_id, timeout_seconds=int(timeout_seconds))
        return _result_for_kind(client, "video", result.raw, task_id, result.credits_consumed, credits_before)


STUDIO_CLASS_MAPPINGS = {
    "KIE_Next_Camera_Director": KIECameraDirectorNode,
    "KIE_Next_Shot_Sequence": KIEShotSequenceNode,
    "KIE_Next_Kling_Omni_Studio": KIEKlingOmniStudioNode,
    "KIE_Next_Seedance_Studio": KIESeedanceStudioNode,
}

STUDIO_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Camera_Director": "KIE • Camera Director",
    "KIE_Next_Shot_Sequence": "KIE • Shot Sequence",
    "KIE_Next_Kling_Omni_Studio": "KIE • Kling 3.0 Omni Studio",
    "KIE_Next_Seedance_Studio": "KIE • Seedance Studio",
}

