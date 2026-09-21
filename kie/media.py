from __future__ import annotations

import io
import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import torch
from PIL import Image

from .client import KIEClient, KIEAPIError


def image_tensor_to_png_bytes(image: torch.Tensor, index: int = 0) -> bytes:
    if not isinstance(image, torch.Tensor):
        raise KIEAPIError("Expected a ComfyUI IMAGE tensor.")
    tensor = image.detach().cpu()
    if tensor.ndim == 3:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 4:
        raise KIEAPIError(f"Expected IMAGE tensor shaped [B,H,W,C], got {tuple(tensor.shape)}")
    if index >= tensor.shape[0]:
        raise IndexError(index)
    frame = tensor[index].clamp(0, 1).numpy()
    if frame.shape[-1] not in (1, 3, 4):
        raise KIEAPIError(f"Unsupported IMAGE channel count: {frame.shape[-1]}")
    array = (frame * 255.0 + 0.5).astype(np.uint8)
    if array.shape[-1] == 1:
        array = array[..., 0]
        mode = "L"
    elif array.shape[-1] == 4:
        mode = "RGBA"
    else:
        mode = "RGB"
    pil = Image.fromarray(array, mode=mode)
    buffer = io.BytesIO()
    pil.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def upload_image_batch(client: KIEClient, image: torch.Tensor, *, prefix: str = "image") -> list[str]:
    tensor = image if image.ndim == 4 else image.unsqueeze(0)
    urls: list[str] = []
    for index in range(int(tensor.shape[0])):
        content = image_tensor_to_png_bytes(tensor, index)
        urls.append(
            client.upload_bytes(
                content,
                filename=f"{prefix}_{uuid.uuid4().hex[:10]}_{index}.png",
                mime_type="image/png",
                upload_path="comfyui/images",
            )
        )
    return urls


def bytes_to_image_tensor(content: bytes) -> torch.Tensor:
    with Image.open(io.BytesIO(content)) as pil:
        pil = pil.convert("RGB")
        array = np.asarray(pil).astype(np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def _result_suffix(url: str, fallback: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix and len(suffix) <= 12 and suffix[1:].isalnum() else fallback


def persist_result_bytes(content: bytes, url: str, *, kind: str, fallback_suffix: str) -> str | None:
    """Archive downloaded KIE media under ComfyUI output and return its path.

    KIE result objects used to live only in ComfyUI's temp directory, so a
    restart could make a successful generation unavailable to the workflow.
    Content-addressed filenames avoid accidental overwrites and duplicate writes.
    """
    try:
        import folder_paths  # type: ignore

        directory = Path(folder_paths.get_output_directory()) / "KIE-Results" / kind
        directory.mkdir(parents=True, exist_ok=True)
        suffix = _result_suffix(url, fallback_suffix)
        path = directory / f"kie_{hashlib.sha256(content).hexdigest()}{suffix}"
        if not path.exists():
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            temporary.write_bytes(content)
            temporary.replace(path)
        return str(path)
    except Exception as exc:
        # Keep a successful remote generation usable if a local output folder is
        # temporarily unavailable. The caller retains the former temp fallback.
        print(f"[KIE Next] Could not archive generated {kind}: {exc}")
        return None


def download_image_tensor(client: KIEClient, url: str) -> torch.Tensor:
    content = client.download_bytes(url)
    persist_result_bytes(content, url, kind="images", fallback_suffix=".png")
    return bytes_to_image_tensor(content)


def _comfy_temp_dir() -> str:
    try:
        import folder_paths  # type: ignore

        root = folder_paths.get_temp_directory()
    except Exception:
        root = tempfile.gettempdir()
    path = os.path.join(root, "kie_nodes_next")
    os.makedirs(path, exist_ok=True)
    return path


def video_to_temp_file(video: Any, *, canonical_h264_sdr: bool = False) -> str:
    path = os.path.join(_comfy_temp_dir(), f"kie_upload_{uuid.uuid4().hex}.mp4")
    if hasattr(video, "save_to"):
        if canonical_h264_sdr:
            # Topaz's remote decoder is stricter than many generation providers.
            # Modern ComfyUI can preserve 10-bit/HDR source characteristics by
            # default, so explicitly materialize an interoperable 8-bit SDR H.264 MP4.
            try:
                video.save_to(
                    path,
                    bit_depth=8,
                    crf=18.0,
                    color_space="sRGB",
                    preset="medium",
                )
            except TypeError as exc:
                raise KIEAPIError(
                    "Topaz Video Upscale requires a current ComfyUI VideoInput implementation "
                    "that supports 8-bit SDR H.264 export. Update ComfyUI and try again."
                ) from exc
        else:
            video.save_to(path)
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            raise KIEAPIError("ComfyUI produced an empty video file before KIE upload.")
        return path
    if isinstance(video, str) and os.path.isfile(video):
        if canonical_h264_sdr:
            raise KIEAPIError(
                "Topaz safe-video normalization requires a ComfyUI VIDEO object, not a raw file path."
            )
        return video
    raise KIEAPIError("Unsupported VIDEO object. Update ComfyUI to a build with VideoInput.save_to().")


def download_video_object(client: KIEClient, url: str):
    content = client.download_bytes(url)
    path = persist_result_bytes(content, url, kind="videos", fallback_suffix=".mp4")
    if path is None:
        path = os.path.join(_comfy_temp_dir(), f"kie_result_{uuid.uuid4().hex}.mp4")
        Path(path).write_bytes(content)
    try:
        from comfy_api.latest import InputImpl  # type: ignore
    except Exception as exc:
        raise KIEAPIError(
            "Your ComfyUI build does not expose comfy_api.latest.InputImpl.VideoFromFile. Update ComfyUI."
        ) from exc
    return InputImpl.VideoFromFile(path)


def audio_to_wav_bytes(audio: Any) -> bytes:
    """Convert a standard ComfyUI AUDIO object to 16-bit PCM WAV bytes."""
    import wave

    if not isinstance(audio, dict) or "waveform" not in audio or "sample_rate" not in audio:
        raise KIEAPIError("Expected a ComfyUI AUDIO object with waveform and sample_rate.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if not isinstance(waveform, torch.Tensor):
        raise KIEAPIError("AUDIO waveform must be a torch.Tensor.")
    tensor = waveform.detach().cpu().float()
    if tensor.ndim == 3:
        tensor = tensor[0]
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 2:
        raise KIEAPIError(f"Unsupported AUDIO waveform shape: {tuple(tensor.shape)}")
    # Comfy uses [channels, samples]. WAV wants interleaved [samples, channels].
    pcm = (tensor.clamp(-1, 1).transpose(0, 1).numpy() * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(int(pcm.shape[1]))
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def upload_audio(client: KIEClient, audio: Any, *, prefix: str = "audio") -> str:
    content = audio_to_wav_bytes(audio)
    return client.upload_bytes(
        content,
        filename=f"{prefix}_{uuid.uuid4().hex[:10]}.wav",
        mime_type="audio/wav",
        upload_path="comfyui/audio",
    )


def download_to_temp_file(client: KIEClient, url: str, suffix: str = "") -> str:
    content = client.download_bytes(url)
    if suffix:
        suffix = suffix if suffix.startswith(".") and suffix[1:].isalnum() else ".bin"
    else:
        suffix = _result_suffix(url, ".bin")
    persistent_path = persist_result_bytes(content, url, kind="files", fallback_suffix=suffix)
    if persistent_path is not None:
        return persistent_path
    path = os.path.join(_comfy_temp_dir(), f"kie_result_{uuid.uuid4().hex}{suffix}")
    Path(path).write_bytes(content)
    return path


def download_audio_object(client: KIEClient, url: str):
    """Download generated audio and decode it to ComfyUI's standard AUDIO dict."""
    content = client.download_bytes(url)
    suffix = _result_suffix(url, ".mp3")
    path = persist_result_bytes(content, url, kind="audio", fallback_suffix=suffix)
    if path is None:
        path = os.path.join(_comfy_temp_dir(), f"kie_audio_{uuid.uuid4().hex}{suffix}")
        Path(path).write_bytes(content)
    try:
        import torchaudio  # ComfyUI ships with torchaudio in standard installs.
        waveform, sample_rate = torchaudio.load(path)
    except Exception as exc:
        # PyAV is also present in modern ComfyUI and handles mp3/aac reliably.
        try:
            import av  # type: ignore
            frames = []
            with av.open(path) as container:
                stream = container.streams.audio[0]
                sample_rate = int(stream.codec_context.sample_rate or 44100)
                channels = int(getattr(stream, "channels", 0) or 1)
                for frame in container.decode(stream):
                    arr = torch.from_numpy(frame.to_ndarray())
                    if arr.ndim == 1:
                        arr = arr.unsqueeze(0)
                    if arr.shape[0] != channels and arr.shape[-1] == channels:
                        arr = arr.transpose(0, 1)
                    frames.append(arr.float())
            if not frames:
                raise RuntimeError("No audio frames decoded")
            waveform = torch.cat(frames, dim=1)
            # Normalize integer PCM returned by PyAV.
            if waveform.abs().max() > 2.0:
                waveform = waveform / 32768.0
        except Exception as fallback_exc:
            raise KIEAPIError(
                f"Generated audio downloaded, but ComfyUI could not decode it ({exc}; {fallback_exc}). URL: {url}"
            ) from fallback_exc
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    return {"waveform": waveform.unsqueeze(0), "sample_rate": int(sample_rate)}

