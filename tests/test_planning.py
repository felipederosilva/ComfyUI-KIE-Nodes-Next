import json
import unittest

from test_generated import load_plugin


class TestShotPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes.planning import build_shot_draft, review_shot_plan
        cls.build_draft = staticmethod(build_shot_draft)
        cls.review = staticmethod(review_shot_plan)

    def test_draft_preserves_scene_text_and_distributes_exact_duration(self):
        first = "A woman enters the station and sees the last train."
        second = "She runs along the platform while the camera follows."
        proposed, total, notes = self.build_draft(first + "\n\n" + second, "paragraphs", 17, 6)
        shots = json.loads(proposed)
        self.assertEqual([s["prompt"] for s in shots], [first, second])
        self.assertEqual(sum(s["duration"] for s in shots), total)
        self.assertEqual(total, 17)
        self.assertTrue(all(1 <= s["duration"] <= 15 for s in shots))
        self.assertTrue(all(s["camera"]["movement"] == "locked-off" for s in shots))
        self.assertIn("Text preserved", notes)

    def test_excess_segments_are_rejected_without_silent_truncation(self):
        with self.assertRaisesRegex(ValueError, "Found 3 segments"):
            self.build_draft("one\ntwo\nthree", "one line per shot", 6, 2)
        with self.assertRaisesRegex(ValueError, "must be"):
            self.build_draft("one\n\ntwo", "paragraphs", 31, 6)

    def test_review_override_feeds_same_storyboard_schema(self):
        draft_result = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Script_To_Shot_Draft"]().build(
            "First scene", "paragraphs", 5, 6)
        draft = draft_result["result"][0]
        self.assertEqual(draft_result["ui"]["kie_shot_plan"], [draft])
        edited = json.loads(draft)
        edited[0]["prompt"] = "A deliberate close-up"
        edited[0]["camera"]["shot_size"] = "close-up"
        review = self.plugin.NODE_CLASS_MAPPINGS["KIE_Next_Shot_Plan_Review"]().review(draft, json.dumps(edited))["result"]
        from kie_next_testpkg.nodes.storyboard import build_storyboard
        sheet, metadata = build_storyboard(review[0], {})
        self.assertEqual(metadata["shots"][0]["prompt"], "A deliberate close-up")
        self.assertEqual(tuple(sheet.shape), (1, 420, 512, 3))
        with self.assertRaisesRegex(ValueError, "duration"):
            self.review('[{"prompt":"a","duration":true}]')

    def test_editorial_rhythms_propose_camera_without_rewriting_source(self):
        from kie_next_testpkg.nodes.planning import VISUAL_RHYTHMS
        from kie_next_testpkg.nodes.studio import SHOT_SIZES, ANGLES, CAMERA_MOVES, LENSES
        source = ["Introduce the location.", "The subject crosses the room.", "Reveal the object on the table."]
        for rhythm in VISUAL_RHYTHMS:
            with self.subTest(rhythm=rhythm):
                proposal, total, note = self.build_draft("\n\n".join(source), "paragraphs", 12, 6, rhythm)
                shots = json.loads(proposal)
                self.assertEqual([shot["prompt"] for shot in shots], source)
                self.assertEqual(total, 12)
                self.assertEqual(len({shot["editorial_intent"] for shot in shots}) > 1, rhythm != "neutral")
                for shot in shots:
                    camera = shot["camera"]
                    self.assertIn(camera["shot_size"], SHOT_SIZES)
                    self.assertIn(camera["angle"], ANGLES)
                    self.assertIn(camera["movement"], CAMERA_MOVES)
                    self.assertIn(camera["lens"], LENSES)
                    self.assertEqual(shot["direction_mode"], "prompt_guidance")
                self.assertIn("prompt text", note)

    def test_suggested_camera_reaches_kling_as_prompt_guidance(self):
        from kie_next_testpkg.nodes.studio import KIEKlingOmniStudioNode, _studio_report
        plan, total, _ = self.build_draft("Open on the street.\n\nA person turns toward camera.\n\nThe letter is revealed.",
                                          "paragraphs", 15, 6, "cinematic reveal")
        model, payload = KIEKlingOmniStudioNode().prepare_request(
            prompt="A single continuous scene", shot_mode="manual shot sequence",
            resolution="720p", aspect_ratio="16:9", duration=total, audio=False,
            shot_sequence_json=plan, dry_run=True)
        self.assertEqual(len(payload["multi_prompt"]), 3)
        self.assertIn("dolly in movement", payload["multi_prompt"][1]["prompt"])
        self.assertIn("push-in with parallax movement", payload["multi_prompt"][2]["prompt"])
        self.assertTrue(_studio_report(model, payload)["valid"])


if __name__ == "__main__":
    unittest.main()
