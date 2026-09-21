import base64
import json
import pathlib
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for browser migration tests")
class TestWidgetMigrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "js" / "widget_migrations.js").read_bytes()
        cls.module_url = "data:text/javascript;base64," + base64.b64encode(source).decode("ascii")

    def run_migration(self, node_type, names, values):
        script = f"""
            const mod = await import({json.dumps(self.module_url)});
            const values = {json.dumps(values)};
            const changed = mod.migrateWan3WidgetValues(
                {json.dumps(node_type)},
                {json.dumps(names)},
                values
            );
            console.log(JSON.stringify({{changed, values}}));
        """
        result = subprocess.run(
            [NODE, "--input-type=module", "--eval", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_repairs_saved_wan_prime_widget_shift(self):
        names = [
            "prompt", "reference_file_urls", "reference_link_urls", "resolution",
            "aspect_ratio", "duration", "audio", "seed", "control_after_generate",
            "nsfw_checker", "timeout_seconds", "callback_url",
        ]
        values = ["prompt", "[]", "[]", "720P", "9:16", 10, True, "randomize", False, 1200, "", ""]
        result = self.run_migration("KIE_Next_wan_3_0_video_prime_7a7b762c", names, values)
        self.assertTrue(result["changed"])
        self.assertEqual(result["values"][6:], [True, 0, "randomize", False, 1200, ""])

    def test_corrected_values_are_left_unchanged(self):
        names = ["audio", "seed", "control_after_generate", "nsfw_checker", "timeout_seconds", "callback_url"]
        values = [True, 42, "fixed", False, 1200, ""]
        result = self.run_migration("KIE_Next_wan_3_0_video_prime_7a7b762c", names, values)
        self.assertFalse(result["changed"])
        self.assertEqual(result["values"], values)


if __name__ == "__main__":
    unittest.main()

