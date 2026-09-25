import json
import math
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import torch

from test_generated import load_plugin


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.assembly import fit_music
        cls.fit_music = staticmethod(fit_music)
        from kie_next_testpkg.nodes.assembly import mix_overlay, peak_protect, duck_music_for_dialogue
        cls.mix_overlay = staticmethod(mix_overlay)
        cls.peak_protect = staticmethod(peak_protect)
        cls.duck_music_for_dialogue = staticmethod(duck_music_for_dialogue)

    def test_fit_pad_fade_and_peak_safety(self):
        audio = {"waveform": torch.ones(1, 1, 100) * 0.8, "sample_rate": 10000}
        fitted, report = self.fit_music(audio, 0.02, 12, "pad silence", 0.001)
        self.assertEqual(tuple(fitted["waveform"].shape), (1, 1, 200))
        self.assertEqual(float(fitted["waveform"][0, 0, -1]), 0)
        self.assertLessEqual(float(fitted["waveform"].abs().max()), 1.0)
        self.assertGreater(report["peak_safety_reduction_db"], 0)

    def test_short_music_loop_avoids_hard_join(self):
        original = torch.linspace(-0.5, 0.5, 1000).reshape(1, 1, -1)
        fitted, report = self.fit_music({"waveform": original, "sample_rate": 10000},
                                        0.3, 0, "loop with crossfade", 0)
        self.assertEqual(fitted["waveform"].shape[-1], 3000)
        self.assertEqual(report["short_music_policy"], "loop with crossfade")
        with self.assertRaisesRegex(ValueError, "more than 64 loops"):
            self.fit_music({"waveform": original, "sample_rate": 10000},
                           10, 0, "loop with crossfade", 0)

    def test_rejects_invalid_audio(self):
        with self.assertRaises(ValueError):
            self.fit_music({"waveform": torch.zeros(1, 3, 5), "sample_rate": 48000},
                           1, 0, "pad silence", 0)

    def test_dialogue_and_effect_can_mix_at_timed_position(self):
        base = {"waveform": torch.zeros(1, 2, 8000), "sample_rate": 8000}
        effect = {"waveform": torch.ones(1, 1, 800) * 0.4, "sample_rate": 8000}
        mixed = self.mix_overlay(base, effect, 0.5)
        self.assertEqual(float(mixed["waveform"][0, 0, 3999]), 0.0)
        self.assertAlmostEqual(float(mixed["waveform"][0, 1, 4000]), 0.4, places=5)
        self.assertAlmostEqual(float(mixed["waveform"][0, 1, 4799]), 0.4, places=5)
        self.assertEqual(float(mixed["waveform"][0, 0, 4800]), 0.0)
        safe, reduction = self.peak_protect(self.mix_overlay(mixed, effect, 0.5, 12))
        self.assertGreater(reduction, 0)
        self.assertLessEqual(float(safe["waveform"].abs().max()), 1.0)

    def test_dialogue_ducking_only_lowers_music_around_voice(self):
        music = {"waveform": torch.ones(1, 2, 16000) * 0.5, "sample_rate": 8000}
        voice = torch.zeros(1, 1, 16000)
        voice[..., 4000:8000] = 0.25
        ducked, report = self.duck_music_for_dialogue(
            music, {"waveform": voice, "sample_rate": 8000}, 12)
        self.assertAlmostEqual(float(ducked["waveform"][0, 0, 800]), 0.5, places=4)
        self.assertLess(float(ducked["waveform"][0, 0, 6000]), 0.15)
        self.assertAlmostEqual(float(ducked["waveform"][0, 0, 12000]), 0.5, places=4)
        self.assertAlmostEqual(report["detected_dialogue_seconds"], 0.5, places=2)
        with self.assertRaisesRegex(ValueError, "between 0 and 30"):
            self.duck_music_for_dialogue(music, {"waveform": voice, "sample_rate": 8000}, 31)

    def test_native_comfy_assembly_writes_video_and_music(self):
        try:
            import comfy_api.latest
        except ImportError:
            self.skipTest("ComfyUI core is not on the unit-test import path; run this test inside ComfyUI.")
        import av
        from comfy_api.latest import InputImpl, Types
        from kie_next_testpkg.nodes.assembly import KIEAssembleVideoNode

        frames_a = torch.zeros(4, 32, 32, 3)
        frames_b = torch.ones(4, 32, 32, 3)
        a = InputImpl.VideoFromComponents(Types.VideoComponents(images=frames_a, frame_rate=Fraction(4)))
        b = InputImpl.VideoFromComponents(Types.VideoComponents(images=frames_b, frame_rate=Fraction(4)))
        samples = torch.sin(torch.linspace(0, 2 * math.pi * 440 * 2, 16000)).reshape(1, 1, -1) * 0.2
        voice = torch.zeros(1, 1, 16000)
        voice[..., 4000:8000] = 0.2
        result, report_json = KIEAssembleVideoNode().assemble(
            a, {"waveform": samples, "sample_rate": 8000}, -6, "pad silence", 0.1,
            video_2=b, dialogue_audio={"waveform": voice, "sample_rate": 8000})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "assembly.mp4"
            result.save_to(str(path))
            self.assertGreater(path.stat().st_size, 1000)
            with av.open(str(path)) as container:
                self.assertEqual(len(container.streams.video), 1)
                self.assertEqual(len(container.streams.audio), 1)
                self.assertEqual(sum(1 for _ in container.decode(video=0)), 8)
        self.assertEqual(json.loads(report_json)["take_count"], 2)
        self.assertGreater(json.loads(report_json)["detected_dialogue_seconds"], 0)
