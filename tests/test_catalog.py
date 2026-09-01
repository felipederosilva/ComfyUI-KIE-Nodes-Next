import json
import pathlib
import unittest
import os
import tempfile
from unittest.mock import patch

from kie.catalog import _extract_endpoint, _extract_models, _extract_example_query, _extract_path_params, _parse_llms_index, load_catalog, sync_catalog


class TestCatalog(unittest.TestCase):

    def test_index_only_keeps_every_api_page_without_fetching_each_doc(self):
        llms = """# docs\n## API Docs\n- Image Models > Demo [One](https://docs.kie.ai/market/demo/one.md): docs\n- Suno API [Two](https://docs.kie.ai/suno-api/two.md): docs\n- CN [三](https://docs.kie.ai/cn/demo/three.md): docs\n"""

        class Response:
            text = llms
            def raise_for_status(self):
                return None

        class Session:
            headers = {}
            def get(self, url, timeout=None):
                self.assert_url = url
                return Response()

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"KIE_NODES_NEXT_CONFIG_DIR": tmp}, clear=False), patch("kie.catalog.requests.Session", return_value=Session()):
            result = sync_catalog(index_only=True)
            catalog = load_catalog()
            self.assertTrue(result["ok"])
            self.assertFalse(result["deep_sync_complete"])
            self.assertEqual(len(catalog["operations"]), 2)
            self.assertTrue(all(not op["resolved"] for op in catalog["operations"]))

    def test_unique_curated_model_ids(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        catalog = json.loads((root / "models" / "catalog.json").read_text(encoding="utf-8"))
        ids = [m["model"] for m in catalog["models"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("bytedance/seedance-2-5", ids)
        self.assertIn("kling-3.0/video", ids)

    def test_llms_index_only_keeps_english_api_docs(self):
        text = """
# KIE
- [Quick Start](https://docs.kie.ai/market/quickstart.md): no
## API Docs
- market / kling > [Kling 3](https://docs.kie.ai/market/kling/v3.md): docs
- suno > [Generate Music](https://docs.kie.ai/suno-api/generate-music.md): docs
- cn > [Chinese](https://docs.kie.ai/cn/suno-api/generate-music.md): docs
"""
        rows = _parse_llms_index(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "Kling 3")
        self.assertEqual(rows[1]["title"], "Generate Music")

    def test_extract_endpoint_multiline_and_curl(self):
        self.assertEqual(_extract_endpoint("POST\n\n/api/v1/jobs/createTask\n"), ("POST", "/api/v1/jobs/createTask"))
        self.assertEqual(
            _extract_endpoint("curl --location 'https://api.kie.ai/api/v1/veo/generate' --data '{\"x\":1}'"),
            ("POST", "https://api.kie.ai/api/v1/veo/generate"),
        )
        self.assertEqual(
            _extract_endpoint("POST\n\nhttps://kieai.redpandaai.co/api/file-base64-upload\n"),
            ("POST", "https://kieai.redpandaai.co/api/file-base64-upload"),
        )

    def test_extract_models(self):
        text = '{"model":"gpt-5-6-sol"}\n{"model": "veo3_fast"}\nmodel="veo3_fast"'
        self.assertEqual(_extract_models(text), ["gpt-5-6-sol", "veo3_fast"])

    def test_query_and_path_parameter_discovery(self):
        text = 'curl --location "https://api.kie.ai/api/v1/demo?taskId=abc123&format=json"'
        q = _extract_example_query(text)
        self.assertEqual(q["taskId"], "abc123")
        self.assertEqual(q["format"], "json")
        self.assertEqual(_extract_path_params("/api/v1/task/{taskId}/files/:fileId"), ["taskId", "fileId"])


if __name__ == "__main__":
    unittest.main()

