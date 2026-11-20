import io
import json
from pathlib import Path

from PIL import Image

from kie import media, model_outputs


def _raster_bytes(mode, size, color):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _stub_storage(monkeypatch, tmp_path):
    def save(content, url, *, kind, fallback_suffix):
        path = tmp_path / f"result-{len(list(tmp_path.iterdir()))}{fallback_suffix}"
        path.write_bytes(content)
        return str(path)
    monkeypatch.setattr(media, "persist_result_bytes", save)
    monkeypatch.setattr(model_outputs, "persist_result_bytes", save)


def test_transparency_and_original_path(monkeypatch, tmp_path):
    _stub_storage(monkeypatch, tmp_path)
    data = _raster_bytes("RGBA", (3, 2), (0, 128, 255, 64))
    client = type("Client", (), {"download_bytes": lambda self, url: data})()
    image, mask, durations, path = media.download_image_asset(client, "https://test.example/no-suffix")

    assert tuple(image.shape) == (1, 2, 3, 3)
    assert abs(float(mask[0, 0, 0]) - (1 - 64 / 255)) < 1e-6
    assert durations == []
    assert Path(path).suffix == ".png"
    assert Path(path).read_bytes() == data


def test_animated_gif_returns_all_frames_and_timing(monkeypatch, tmp_path):
    _stub_storage(monkeypatch, tmp_path)
    buffer = io.BytesIO()
    frames = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:], duration=[100, 250])
    client = type("Client", (), {"download_bytes": lambda self, url: buffer.getvalue()})()
    image, mask, durations, path = media.download_image_asset(client, "https://test.example/no-suffix")

    assert tuple(image.shape) == (2, 2, 2, 3)
    assert image[0, 0, 0].tolist() == [1, 0, 0]
    assert image[1, 0, 0].tolist() == [0, 0, 1]
    assert mask.max() == 0
    assert durations == [100, 250]
    assert Path(path).suffix == ".gif"


def test_svg_is_preserved_as_file_with_no_raster(monkeypatch, tmp_path):
    _stub_storage(monkeypatch, tmp_path)
    data = b'<svg xmlns="http://www.w3.org/2000/svg" />'
    client = type("Client", (), {"download_bytes": lambda self, url: data})()
    image, (mask, path, durations) = model_outputs.model_image_result(
        client, "gpt-image-2-6/flare-text-to-image", {}, "https://test.example/no-suffix", "test", "svg",
    )

    assert image is None and mask is None
    assert json.loads(durations) == []
    assert Path(path).suffix == ".svg"
    assert Path(path).read_bytes() == data


def test_seedream_layer_stack_preserves_bbox_order_and_alpha(monkeypatch, tmp_path):
    _stub_storage(monkeypatch, tmp_path)
    base = "https://test.example/base"
    urls = [base, "https://test.example/one.png", "https://test.example/two.png"]
    pixels = {base: _raster_bytes("RGB", (8, 6), "black")}
    pixels.update({url: _raster_bytes("RGBA", (4, 3), (159, 255, 255, 0)) for url in urls[1:]})
    requested = []

    class Client:
        def download_bytes(self, url):
            requested.append(url)
            return pixels[url]

    layers = [
        {"z_index": 2, "url": urls[2], "name": "First in response", "bounding_box": {"absolute": [3, 1, 8, 4]}},
        {"z_index": 0, "url": base},
        {"z_index": 1, "url": urls[1], "bounding_box": {"absolute": [0, 0, 4, 3]}},
    ]
    record = {"resultJson": json.dumps({"resultUrls": urls, "resultObject": {"layers_data": layers}})}

    preferred = model_outputs.primary_result_url(record, urls[1:], kind="image")
    result, (mask, stack, metadata) = model_outputs.model_image_result(
        Client(), "seedream/5-5-layer-decomposition", record, preferred, "test", "png",
    )

    assert requested.count(base) == 1
    assert result is stack["layers"][0]["image"]
    assert mask.max() == 0
    assert stack["canvas"] == (8, 6)
    assert [layer["z_index"] for layer in stack["layers"]] == [0, 1, 2]
    top = stack["layers"][-1]
    assert (top["x"], top["y"], top["w"], top["h"]) == (3, 1, 5, 3)
    assert top["mask"].min() == 1
    assert json.loads(metadata) == layers


def test_seedance_last_frame_is_separate_from_video(monkeypatch):
    monkeypatch.setattr(model_outputs, "download_video_object", lambda client, url: ("video", url))
    monkeypatch.setattr(model_outputs, "download_image_tensor", lambda client, url: ("image", url))
    video, frame = "https://test.example/video", "https://test.example/still.jpeg"
    record = {"response": {"resultUrls": [video]}, "resultJson": json.dumps({"lastFrameUrl": [frame]})}

    preferred = model_outputs.primary_result_url(record, [frame], kind="video")
    model = "bytedance/seedance-2-5-flash"
    assert model_outputs.model_video_result(None, model, record, preferred, "test") == (
        ("video", video), (("image", frame), frame),
    )
    assert model_outputs.primary_result_url({"response": {"lastFrameUrl": [frame]}}, [frame], kind="video") == ""
    assert model_outputs.model_video_result(None, model, {}, preferred, "test") == (("video", video), (None, ""))


def test_gemini_omni_stills_and_synchronous_asset_identifiers(monkeypatch):
    monkeypatch.setattr(model_outputs, "download_video_object", lambda client, url: ("video", url))
    monkeypatch.setattr(model_outputs, "download_image_tensor", lambda client, url: ("image", url))
    video, first, last = "https://test.example/video", "https://test.example/first", "https://test.example/last"
    record = {"response": {"resultUrls": [video], "firstFrameUrl": first, "lastFrameUrl": [last]}}
    assert model_outputs.model_video_result(None, "google/gemini-omni-flash-1-2", record, video, "test") == (
        ("video", video), (("image", first), first, ("image", last), last),
    )
    assert model_outputs.model_output_slots("google/gemini-omni-flash-1-2-extend", "video") == ()

    audio = {"data": {"audioId": "voice-1", "name": "Voice"}}
    assert model_outputs.direct_asset_result("/api/v1/omni/audio/create", audio) == ("voice-1", "Voice")
    character = {"data": {"characterId": "character-1", "characterName": "Jenny", "imageUrl": first}}
    assert model_outputs.direct_asset_result("/api/v1/omni/character/create", character) == ("character-1", "Jenny", first, "")


def test_kling_ordered_urls_do_not_force_all_8k_images_to_decode(monkeypatch):
    first, second = "https://test.example/first", "https://test.example/second"
    loaded = []
    monkeypatch.setattr(model_outputs, "download_image_tensor", lambda client, url: loaded.append(url) or "image")
    assert model_outputs.model_image_result(
        None, "kling-4-0/image", {"response": {"resultUrls": [first, second]}}, first, "test", "png",
    ) == ("image", ([first, second],))
    assert loaded == [first]


def test_nemotron_keeps_transcript_and_documented_speaker_timestamps(monkeypatch, tmp_path):
    _stub_storage(monkeypatch, tmp_path)
    url = "https://test.example/transcript.json"
    record = {"resultJson": json.dumps({"resultObject": {"text": "Hello", "duration": 2.1, "url": url}})}
    detail = {
        "text_with_speakers": "<spk:0> Hello",
        "words": [{"word": "Hello", "start": 0.2, "end": 0.6, "speaker": "0"}],
        "diarization": [{"speaker": 0, "start": 0.2, "end": 0.6}],
    }
    client = type("Client", (), {"download_bytes": lambda self, url: json.dumps(detail).encode()})()
    transcript, (result_url, duration, speaker_text, words, turns, path) = model_outputs.nemotron_result(client, record, "test")

    assert (transcript, result_url, duration, speaker_text) == ("Hello", url, 2.1, "<spk:0> Hello")
    assert json.loads(words) == detail["words"]
    assert json.loads(turns) == detail["diarization"]
    assert json.loads(Path(path).read_bytes()) == detail
