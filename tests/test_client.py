import json
import unittest

from kie.client import KIEClient


class TestResultParsing(unittest.TestCase):
    def test_result_urls_json_string(self):
        data = {"resultJson": json.dumps({"resultUrls": ["https://a.test/a.png", "https://a.test/b.png"]})}
        self.assertEqual(KIEClient.extract_result_urls(data), ["https://a.test/a.png", "https://a.test/b.png"])

    def test_nested_dedup(self):
        data = {
            "resultJson": json.dumps({
                "outputs": [{"url": "https://a.test/a.mp4"}],
                "resultUrl": "https://a.test/a.mp4"
            })
        }
        self.assertEqual(KIEClient.extract_result_urls(data), ["https://a.test/a.mp4"])

    def test_plain_url(self):
        self.assertEqual(
            KIEClient.extract_result_urls({"resultJson": "https://a.test/result.jpg"}),
            ["https://a.test/result.jpg"],
        )


if __name__ == "__main__":
    unittest.main()


class _FakeResponse:
    ok = True
    status_code = 200
    text = 'data: {"type":"response.output_text.delta","delta":"Hello"}\n\ndata: [DONE]\n'
    headers = {"Content-Type": "text/event-stream"}

    def json(self):
        raise ValueError("not json")


class _FakeSession:
    def request(self, *args, **kwargs):
        return _FakeResponse()


class TestRawAPI(unittest.TestCase):
    def test_sse_is_normalized(self):
        from kie.client import KIEConfig
        client = KIEClient(KIEConfig(api_key="x", max_retries=0), session=_FakeSession())
        payload = client.raw_api_request("POST", "/codex/v1/responses", body={"model": "gpt-5-6-sol"})
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(payload["stream_events"][0]["delta"], "Hello")

