import unittest
from copy import deepcopy
from unittest.mock import patch
import time

from kie.catalog import _extract_openapi_request, _merge_catalogs
from kie.market_catalog import merge_market_schemas, request_definition, sync_market_schemas


def document(model, controls):
    return {"paths": {"/api/v1/jobs/createTask": {"post": {"requestBody": {"content": {
        "application/json": {"schema": {"type": "object", "properties": {
            "model": {"type": "string", "enum": [model]}, "input": controls}}}}}}}}}


class TestMarketCatalog(unittest.TestCase):
    def test_schema_model_and_required_controls_survive_missing_examples(self):
        model = {"model": "kling-4.0/keyframe-to-video", "title": "Kling 4.0 Keyframe To Video",
                 "provider": "Kling", "taskType": ["Image to Video"]}
        schema = document(model["model"], {"type": "object", "required": ["prompt"], "properties": {
            "prompt": {"type": "string"}, "keyframe_urls": {"type": "array", "maxItems": 8},
            "duration": {"type": "integer", "minimum": 3, "maximum": 30, "default": 5}}})
        original = {"operations": [], "models": []}
        result = merge_market_schemas(original, [model], {model["model"]: {"openapi": schema}}, verified_at=100)
        op = result["operations"][0]
        self.assertEqual(op["market_model"], model["model"])
        self.assertTrue(op["parameter_hints"]["prompt"]["required"])
        self.assertFalse(op["parameter_hints"]["keyframe_urls"]["required"])
        self.assertEqual(op["parameter_hints"]["duration"]["maximum"], 30)
        self.assertEqual(original, {"operations": [], "models": []})

    def test_local_refs_decode_component_names_without_stripping_spaces(self):
        doc = document("example/model", {"$ref": "#/components/schemas/input%20schema%20"})
        doc["components"] = {"schemas": {"input schema ": {"type": "object", "required": ["image_url"],
            "properties": {"image_url": {"type": "string"}}}}}
        result = request_definition(doc, "/api/v1/jobs/createTask", "POST")
        self.assertEqual(result["schema"]["required"], ["image_url"])

    def test_suno_transport_id_does_not_replace_inner_version(self):
        schema = document("ai-music-api/generate", {"type": "object", "properties": {
            "model": {"type": "string", "enum": ["V5", "V6"]}, "prompt": {"type": "string"}}})
        op = {"title": "Generate Music", "label": "Suno • Generate Music", "family": "Music Models > Suno",
              "docs_url": "https://docs.kie.ai/suno-api/generate-music.md", "models": ["V5"],
              "market_model": "ai-music-api/generate", "endpoint": "/api/v1/jobs/createTask"}
        model = {"model": "ai-music-api/generate", "title": "Music", "taskType": ["Text to Music"]}
        result = merge_market_schemas({"operations": [op]}, [model], {model["model"]: {"openapi": schema}})
        self.assertEqual(len(result["operations"]), 1)
        self.assertEqual(result["operations"][0]["models"], ["V5", "V6"])
        self.assertEqual(result["operations"][0]["docs_url"], op["docs_url"])

    def test_unavailable_schema_is_reported_without_an_invented_endpoint(self):
        model = {"model": "future/model", "title": "Future model"}
        result = merge_market_schemas({"operations": []}, [model], {model["model"]: {"openapi": None}})
        self.assertEqual(result["operations"], [])
        self.assertEqual(result["market_schemas_unavailable"], [model["model"]])

    def test_oneof_keeps_mode_requirements_instead_of_losing_all_controls(self):
        schema = document('example/model', {'oneOf': [
            {'title': 'Existing task', 'required': ['task_id'], 'properties': {'task_id': {'type': 'string'}}},
            {'title': 'New image', 'required': ['image_url'], 'properties': {'image_url': {'type': 'string'}}}]})
        result = request_definition(schema, '/api/v1/jobs/createTask', 'POST')['schema']
        self.assertEqual(set(result['properties']), {'task_id', 'image_url'})
        self.assertEqual(result['required'], [])
        self.assertEqual(result['oneOf'][1]['required'], ['image_url'])

    def test_verified_schema_is_not_overwritten_by_stale_richer_cache(self):
        current = {"docs_url": "https://docs.kie.ai/test", "schema_verified_at": 200,
                   "parameter_hints": {"duration": {"maximum": 30}}}
        stale = {**deepcopy(current), "schema_verified_at": 100,
                 "parameter_hints": {"duration": {"maximum": 10}, "obsolete": {}}}
        self.assertEqual(_merge_catalogs({"operations": [current]}, {"operations": [stale]})["operations"][0], current)

    def test_fresh_schema_cache_refreshes_market_metadata_without_refetching(self):
        urls = []

        class Session:
            headers = {}
            def get(self, url, timeout):
                urls.append(url)
                class Response:
                    def raise_for_status(self):
                        pass
                    def json(self):
                        return {'code': 200, 'data': {'models': [{'model': 'example/model', 'pricingDesc': 'new price'}]}}
                return Response()

        catalog = {'models': [{'model': 'example/model', 'schema_available': True,
                              'market_schema_verified_at': int(time.time())}], 'operations': []}
        with patch('kie.market_catalog.requests.Session', return_value=Session()):
            result = sync_market_schemas(catalog, 'test-only-key')
        self.assertEqual(urls, ['https://api.kie.ai/api/v1/models'])
        self.assertEqual(result['models'][0]['pricing_description'], 'new price')
        self.assertNotIn('test-only-key', str(result))
