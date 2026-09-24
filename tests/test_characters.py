import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_plugin():
    name = "kie_next_testpkg"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestCharacterPacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        from kie_next_testpkg.nodes import characters
        cls.characters = characters

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / "character_packs"
        self.patch_root = patch.object(self.characters, "character_packs_root", return_value=self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.temp.cleanup)
        self.image = torch.ones((1, 12, 10, 3), dtype=torch.float32) * 0.5

    def save(self, **overrides):
        args = {
            "name": "Maya",
            "version": "1",
            "identity_description": "Woman with dark curly hair and a silver streak.",
            "visual_style": "Cinematic naturalism",
            "continuity_rules": "Keep face, hairline, and proportions stable.",
            "portrait": self.image,
        }
        args.update(overrides)
        return self.characters.KIESaveCharacterPackNode().save_pack(**args)

    def test_save_load_and_reference_round_trip(self):
        saved, manifest_json = self.save(full_body=self.image)
        manifest = json.loads(manifest_json)
        self.assertEqual(manifest["pack_id"], "maya__v1")
        self.assertTrue((pathlib.Path(saved["directory"]) / "portrait.png").is_file())

        label = next(iter(self.characters._available_packs()))
        loaded, identity_prompt, loaded_json = self.characters.KIELoadCharacterPackNode().load_pack(label)
        self.assertIn("dark curly hair", identity_prompt)
        self.assertEqual(json.loads(loaded_json)["version"], "1")
        image, prompt = self.characters.KIECharacterReferenceNode().load_reference(loaded, "full_body", "red coat")
        self.assertEqual(tuple(image.shape), (1, 12, 10, 3))
        self.assertIn("red coat", prompt)

    def test_identical_save_is_idempotent_but_changes_require_new_version(self):
        first, _ = self.save()
        second, _ = self.save()
        self.assertEqual(first["manifest"]["content_sha256"], second["manifest"]["content_sha256"])
        with self.assertRaisesRegex(ValueError, "different contents"):
            self.save(identity_description="A visibly different person")

    def test_real_person_requires_permission_confirmation(self):
        with self.assertRaisesRegex(ValueError, "permission"):
            self.save(real_person_reference=True, consent_confirmed=False)

    def test_consistency_plan_is_manual_and_uses_available_views(self):
        saved, _ = self.save(full_body=self.image, profile=self.image)
        character = saved
        node = self.characters.KIECharacterConsistencyPlanNode()
        prompt, view, matrix_json = node.build_plan(character, "portrait · profile", "blue coat")
        matrix = json.loads(matrix_json)
        self.assertEqual(view, "profile")
        self.assertIn("same character, not a redesign", prompt)
        self.assertIn("blue coat", next(case["prompt"] for case in matrix if case["case"] == "continuity · changed scene"))
        self.assertEqual(len(matrix), 8)
        portrait_only, _ = self.save(name="Luna")
        with self.assertRaisesRegex(ValueError, "needs a full_body view"):
            node.build_plan(portrait_only, "full body · wide frame")

    def test_portrait_is_required(self):
        with self.assertRaisesRegex(ValueError, "portrait"):
            self.save(portrait=None)

    def test_nodes_are_registered(self):
        names = self.plugin.NODE_DISPLAY_NAME_MAPPINGS.values()
        self.assertIn("KIE • Save Character Pack", names)
        self.assertIn("KIE • Load Character Pack", names)
        self.assertIn("KIE • Character Reference", names)
        self.assertIn("KIE • Character Consistency Test Plan", names)


if __name__ == "__main__":
    unittest.main()
