"""Local hard-cut assembly with a fitted, explicit complete soundtrack."""
from __future__ import annotations

import json
import math

import torch


def fit_music(audio: dict, duration: float, gain_db: float, short_music: str,
              fade_seconds: float) -> tuple[dict, dict]:
    if not isinstance(audio, dict) or not isinstance(audio.get("waveform"), torch.Tensor):
        raise ValueError("Connect a ComfyUI AUDIO object with waveform and sample_rate.")
    sample_rate = int(audio.get("sample_rate") or 0)
    if sample_rate < 8000 or sample_rate > 192000 or not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError("Music sample rate or video duration is unsupported.")
    tensor = audio["waveform"].detach().cpu().float()
    if tensor.ndim == 2:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 3 or tensor.shape[0] != 1 or tensor.shape[1] not in (1, 2) or tensor.shape[2] == 0:
        raise ValueError("Music must be a non-empty mono or stereo AUDIO waveform.")
    if not -48 <= gain_db <= 12 or not 0 <= fade_seconds <= 10:
        raise ValueError("Use gain between −48 and +12 dB and a fade of 0–10 seconds.")
    if short_music not in {"pad silence", "loop with crossfade"}:
        raise ValueError("Choose pad silence or loop with crossfade for short music.")
    target_samples = round(duration * sample_rate)
    original_samples = tensor.shape[-1]
    if original_samples < target_samples:
        if short_music == "pad silence":
            fitted = torch.nn.functional.pad(tensor, (0, target_samples - original_samples))
        else:
            # Build an overlapping loop with a short equal-power join, not a hard splice.
            overlap = min(round(0.1 * sample_rate), original_samples // 4)
            if overlap < 2:
                raise ValueError("Music is too short for a crossfaded loop; use pad silence.")
            step = original_samples - overlap
            if math.ceil(max(0, target_samples - original_samples) / step) > 64:
                raise ValueError("The soundtrack needs more than 64 loops. Use a longer track or pad silence.")
            fitted = torch.zeros((*tensor.shape[:-1], target_samples), dtype=tensor.dtype)
            fitted[..., :min(original_samples, target_samples)] = tensor[..., :target_samples]
            offset = original_samples
            while offset < target_samples:
                end = min(offset + step, target_samples)
                ramp = torch.linspace(0, math.pi / 2, overlap).reshape(1, 1, -1)
                join_start = offset - overlap
                fitted[..., join_start:offset] = fitted[..., join_start:offset] * torch.cos(ramp) + tensor[..., :overlap] * torch.sin(ramp)
                fitted[..., offset:end] = tensor[..., overlap:overlap + (end - offset)]
                offset = end
    else:
        fitted = tensor[..., :target_samples].clone()
    fitted *= 10 ** (gain_db / 20)
    fade_samples = min(round(fade_seconds * sample_rate), target_samples // 2)
    if fade_samples:
        ramp = torch.linspace(0, 1, fade_samples).reshape(1, 1, -1)
        fitted[..., :fade_samples] *= ramp
        fitted[..., -fade_samples:] *= ramp.flip(-1)
    peak = float(fitted.abs().max())
    safety_reduction_db = 0.0
    if peak > 0.999:
        fitted *= 0.999 / peak
        safety_reduction_db = round(20 * math.log10(peak / 0.999), 2)
    report = {"source_duration_seconds": round(original_samples / sample_rate, 3),
              "target_duration_seconds": round(duration, 3), "short_music_policy": short_music,
              "gain_db": gain_db, "fade_seconds": fade_seconds,
              "peak_safety_reduction_db": safety_reduction_db,
              "source_audio_replaced": True}
    return {"waveform": fitted, "sample_rate": sample_rate}, report


def mix_overlay(base: dict, overlay: dict, at_seconds: float, gain_db: float = 0.0) -> dict:
    if not math.isfinite(at_seconds) or at_seconds < 0 or not -48 <= gain_db <= 12:
        raise ValueError("Overlay position or gain is invalid.")
    sample_rate = int(base["sample_rate"])
    source_rate = int(overlay.get("sample_rate") or 0) if isinstance(overlay, dict) else 0
    waveform = overlay.get("waveform") if isinstance(overlay, dict) else None
    if source_rate < 8000 or source_rate > 192000 or not isinstance(waveform, torch.Tensor):
        raise ValueError("Dialogue/SFX must be a valid ComfyUI AUDIO object.")
    tensor = waveform.detach().cpu().float()
    if tensor.ndim == 2:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 3 or tensor.shape[0] != 1 or tensor.shape[1] not in (1, 2) or tensor.shape[2] == 0:
        raise ValueError("Dialogue/SFX must be non-empty mono or stereo audio.")
    if source_rate != sample_rate:
        try:
            import torchaudio.functional as taf
        except ImportError as exc:
            raise RuntimeError("Resampling dialogue/SFX needs torchaudio in ComfyUI's Python environment.") from exc
        tensor = taf.resample(tensor, source_rate, sample_rate)
    out = base["waveform"].clone()
    if out.shape[1] == 1 and tensor.shape[1] == 2:
        out = out.repeat(1, 2, 1)
    if out.shape[1] == 2 and tensor.shape[1] == 1:
        tensor = tensor.repeat(1, 2, 1)
    offset = round(at_seconds * sample_rate)
    end = min(offset + tensor.shape[-1], out.shape[-1])
    if offset < end:
        out[..., offset:end] += tensor[..., :end - offset] * (10 ** (gain_db / 20))
    return {"waveform": out, "sample_rate": sample_rate}


def peak_protect(audio: dict) -> tuple[dict, float]:
    waveform = audio["waveform"]
    peak = float(waveform.abs().max())
    if peak <= 0.999:
        return audio, 0.0
    return {"waveform": waveform * (0.999 / peak), "sample_rate": audio["sample_rate"]}, round(20 * math.log10(peak / 0.999), 2)


def duck_music_for_dialogue(music: dict, dialogue: dict, reduction_db: float) -> tuple[dict, dict]:
    """Lower the bed around audible dialogue; never infer words or change dialogue gain."""
    if not 0 <= reduction_db <= 30:
        raise ValueError("Dialogue ducking must be between 0 and 30 dB.")
    # Reuse the validated overlay path for mono/stereo conversion and resampling.
    silent = {"waveform": torch.zeros_like(music["waveform"]), "sample_rate": music["sample_rate"]}
    voice = mix_overlay(silent, dialogue, 0.0)["waveform"]
    if reduction_db == 0:
        return music, {"dialogue_duck_db": 0.0, "detected_dialogue_seconds": 0.0}
    rate = int(music["sample_rate"])
    block = max(1, round(rate * 0.02))
    length = voice.shape[-1]
    blocks = math.ceil(length / block)
    padded = torch.nn.functional.pad(voice, (0, blocks * block - length))
    rms = padded.square().mean(dim=1).reshape(blocks, block).mean(dim=1).sqrt()
    active = (rms > 10 ** (-42 / 20)).float().reshape(1, 1, -1)
    if not bool(active.any()):
        return music, {"dialogue_duck_db": reduction_db, "detected_dialogue_seconds": 0.0}
    # A short hold avoids pumping between syllables. Smoothed edges avoid clicks.
    hold = 21
    held = torch.nn.functional.max_pool1d(active, hold, stride=1, padding=hold // 2)
    smoothing = 11
    envelope = torch.nn.functional.avg_pool1d(held, smoothing, stride=1, padding=smoothing // 2)
    envelope = envelope.reshape(-1).repeat_interleave(block)[:length].reshape(1, 1, -1)
    gain = 1 - envelope * (1 - 10 ** (-reduction_db / 20))
    result = music["waveform"].clone() * gain
    return {"waveform": result, "sample_rate": rate}, {
        "dialogue_duck_db": reduction_db,
        "detected_dialogue_seconds": round(float(active.sum()) * block / rate, 3),
    }


class KIEAssembleVideoNode:
    CATEGORY = "KIE Next/Studio/Production"
    FUNCTION = "assemble"
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "assembly_report_json")
    DESCRIPTION = "Concatenate up to four compatible takes with hard cuts. Fit music, optionally duck under dialogue and mix two timed SFX, then use Save Video. Source audio is replaced; connect it separately as dialogue if needed."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video_1": ("VIDEO",), "music": ("AUDIO",),
                             "music_gain_db": ("FLOAT", {"default": -6.0, "min": -48.0, "max": 12.0, "step": 0.5}),
                             "short_music": (["pad silence", "loop with crossfade"], {"default": "pad silence"}),
                             "fade_seconds": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1})},
                "optional": {"video_2": ("VIDEO",), "video_3": ("VIDEO",), "video_4": ("VIDEO",),
                             "dialogue_audio": ("AUDIO",),
                             "dialogue_duck_db": ("FLOAT", {"default": 12.0, "min": 0.0, "max": 30.0, "step": 0.5}),
                             "sfx_1": ("AUDIO",), "sfx_1_time_seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 3600.0, "step": 0.1}),
                             "sfx_2": ("AUDIO",), "sfx_2_time_seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 3600.0, "step": 0.1})}}

    def assemble(self, video_1, music, music_gain_db=-6.0, short_music="pad silence",
                 fade_seconds=1.0, video_2=None, video_3=None, video_4=None,
                 dialogue_audio=None, dialogue_duck_db=12.0, sfx_1=None, sfx_1_time_seconds=0.0,
                 sfx_2=None, sfx_2_time_seconds=0.0):
        from comfy_api.latest import InputImpl

        videos = [video for video in (video_1, video_2, video_3, video_4) if video is not None]
        if any(not callable(getattr(video, "get_duration", None)) for video in videos):
            raise ValueError("Connect ComfyUI VIDEO objects for all takes.")
        dimensions = [video.get_dimensions() for video in videos]
        rates = [video.get_frame_rate() for video in videos]
        if any(value != dimensions[0] for value in dimensions[1:]):
            raise ValueError("All takes need matching dimensions; resize before assembly.")
        if any(value != rates[0] for value in rates[1:]):
            raise ValueError("All takes need matching frame rates; convert before assembly.")
        durations = [float(video.get_duration()) for video in videos]
        if any(not math.isfinite(value) or value <= 0 for value in durations):
            raise ValueError("Every take needs a valid positive duration.")
        soundtrack, report = fit_music(music, sum(durations), float(music_gain_db),
                                       short_music, float(fade_seconds))
        if dialogue_audio is not None:
            soundtrack, duck_report = duck_music_for_dialogue(soundtrack, dialogue_audio, float(dialogue_duck_db))
            report.update(duck_report)
            soundtrack = mix_overlay(soundtrack, dialogue_audio, 0.0)
        effect_cues = []
        for index, audio, moment in ((1, sfx_1, sfx_1_time_seconds), (2, sfx_2, sfx_2_time_seconds)):
            if audio is not None:
                soundtrack = mix_overlay(soundtrack, audio, float(moment))
                effect_cues.append({"effect": index, "time_seconds": float(moment)})
        soundtrack, mix_reduction = peak_protect(soundtrack)
        output = InputImpl.VideoFromList(videos, soundtrack)
        report.update({"take_durations_seconds": [round(value, 3) for value in durations],
                       "take_count": len(videos), "transition": "hard cut",
                       "dialogue_audio_connected": dialogue_audio is not None,
                       "effect_cues": effect_cues, "mix_peak_safety_reduction_db": mix_reduction,
                       "export_next": "Connect video to KIE • Save Video or Preview Video."})
        return output, json.dumps(report, ensure_ascii=False)
