import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_generated import load_plugin


class TestRecipes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes import recipes
        cls.recipes = recipes

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(self.recipes, "recipes_root", return_value=Path(self.temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_recipe_is_reloadable_and_cannot_change_for_same_task(self):
        saver = self.recipes.KIESaveGenerationRecipeNode()
        args = ("kling-3.0-omni/text-to-video", "A wide station shot", "task-123", 4.25)
        recipe_id, encoded = saver.save_recipe(*args, camera_plan_json='{"movement":"dolly in"}',
                                               references_json='["portrait.png"]',
                                               result_urls_json='["https://example.test/result.mp4"]')
        self.assertEqual(json.loads(encoded)["camera_plan"]["movement"], "dolly in")
        self.assertNotIn("api_key", encoded)
        loaded = self.recipes.KIELoadGenerationRecipeNode().load_recipe(recipe_id)
        self.assertEqual(loaded[:3], args[:3])
        self.assertEqual(saver.save_recipe(*args, camera_plan_json='{"movement":"dolly in"}',
                                           references_json='["portrait.png"]',
                                           result_urls_json='["https://example.test/result.mp4"]')[0], recipe_id)
        with self.assertRaisesRegex(ValueError, "different saved recipe"):
            saver.save_recipe(args[0], "A different prompt", "task-123", 4.25)

    def test_bad_reference_json_is_rejected_before_save(self):
        with self.assertRaisesRegex(ValueError, "references_json"):
            self.recipes.KIESaveGenerationRecipeNode().save_recipe("model", "prompt", "", 0,
                                                                  references_json="not JSON")
        self.assertFalse(list(Path(self.temp.name).glob("*.json")))


if __name__ == "__main__":
    unittest.main()
