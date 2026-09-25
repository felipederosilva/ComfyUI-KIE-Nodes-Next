import json
import unittest

from test_generated import load_plugin


class SFXPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        from kie_next_testpkg.nodes.sfx_prompt import sfx_prompt
        cls.sfx_prompt = staticmethod(sfx_prompt)

    def setUp(self):
        self.sheet = json.dumps({"ambience": "quiet cafe", "cues": [{
            "id": "SFX-01", "time_seconds": 3.5, "description": "ceramic cup lands on table", "status": "editor-verified"}]})

    def test_timed_effect_maps_to_suno_sounds(self):
        prompt, loop, lyrics, time, cue_id = self.sfx_prompt(self.sheet, "timed effect", 1)
        self.assertIn("ceramic cup", prompt)
        self.assertLessEqual(len(prompt), 500)
        self.assertEqual((loop, lyrics, time, cue_id), (False, False, 3.5, "SFX-01"))

    def test_ambience_loop_and_unapproved_rejection(self):
        prompt, loop, lyrics, _, _ = self.sfx_prompt(self.sheet, "ambient loop", 1)
        self.assertTrue(loop)
        self.assertFalse(lyrics)
        self.assertIn("quiet cafe", prompt)
        altered = json.loads(self.sheet)
        altered["cues"][0]["status"] = "visual_guess"
        with self.assertRaisesRegex(ValueError, "editor-verified"):
            self.sfx_prompt(json.dumps(altered), "timed effect", 1)
