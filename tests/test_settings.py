import os
import tempfile
import unittest
from unittest.mock import patch

from kie.client import KIEConfig
from kie.settings import clear_api_key, get_api_key, public_status, save_api_key


class TestSettings(unittest.TestCase):
    def test_saved_key_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"KIE_NODES_NEXT_CONFIG_DIR": tmp, "KIE_API_KEY": ""}, clear=False):
            save_api_key("kie-test-once")
            self.assertEqual(get_api_key(), "kie-test-once")
            self.assertEqual(KIEConfig.from_values().api_key, "kie-test-once")
            clear_api_key()
            self.assertEqual(get_api_key(), "")

    def test_environment_has_priority(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"KIE_NODES_NEXT_CONFIG_DIR": tmp, "KIE_API_KEY": "env-key"}, clear=False):
            save_api_key("saved-key")
            self.assertEqual(get_api_key(), "env-key")

    def test_public_status_masks_saved_secret(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"KIE_NODES_NEXT_CONFIG_DIR": tmp, "KIE_API_KEY": ""}, clear=False):
            secret = "kie-super-secret-ABCD"
            save_api_key(secret, credits=123.0, validation_state="connected")
            status = public_status()
            self.assertTrue(status["configured"])
            self.assertEqual(status["validation_state"], "connected")
            self.assertEqual(status["masked_key"], "••••••••••••ABCD")
            self.assertNotIn(secret, str(status))


if __name__ == "__main__":
    unittest.main()

