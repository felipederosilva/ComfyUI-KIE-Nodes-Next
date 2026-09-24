from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from .settings import get_api_key


DEFAULT_API_BASE = "https://api.kie.ai"
DEFAULT_UPLOAD_BASE = "https://kieai.redpandaai.co"


class KIEAPIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class KIEConfig:
    api_key: str
    api_base: str = DEFAULT_API_BASE
    upload_base: str = DEFAULT_UPLOAD_BASE
    request_timeout: float = 90.0
    max_retries: int = 4

    @classmethod
    def from_values(
        cls,
        api_key: str = "",
        use_env_key: bool = True,
        api_base: str = DEFAULT_API_BASE,
        upload_base: str = DEFAULT_UPLOAD_BASE,
        request_timeout: float = 90.0,
        max_retries: int = 4,
    ) -> "KIEConfig":
        # New default: resolve a key saved once in ComfyUI Settings. Environment
        # variables still take priority for servers/headless installs. Legacy explicit
        # config nodes remain supported for existing workflows.
        key = (get_api_key() if use_env_key else "") or api_key
        key = key.strip()
        if not key:
            raise KIEAPIError(
                "No KIE API key configured. Open ComfyUI Settings → KIE.ai Nodes Next → Connection and paste your API key once."
            )
        return cls(
            api_key=key,
            api_base=api_base.rstrip("/"),
            upload_base=upload_base.rstrip("/"),
            request_timeout=float(request_timeout),
            max_retries=int(max_retries),
        )


@dataclass
class KIEResult:
    task_id: str
    state: str
    urls: list[str]
    credits_consumed: float
    raw: dict[str, Any]


class KIEClient:
    """Small reusable client for KIE Market + file upload APIs."""

    RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self, config: KIEConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _request(
        self,
        method: str,
        url: str,
        *,
        expected_json: bool = True,
        retry: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        attempts = self.config.max_retries + 1 if retry else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=kwargs.pop("timeout", self.config.request_timeout),
                    **kwargs,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    raise KIEAPIError(f"KIE network error: {exc}") from exc
                time.sleep(min(1.5 * (2**attempt), 10.0))
                continue

            if response.status_code in self.RETRYABLE_STATUS and retry and attempt < attempts - 1:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(1.5 * (2**attempt), 10.0)
                except ValueError:
                    delay = min(1.5 * (2**attempt), 10.0)
                time.sleep(max(delay, 0.25))
                continue

            if not response.ok:
                payload = self._safe_json(response)
                msg = self._extract_error_message(payload) or response.text[:500]
                raise KIEAPIError(
                    f"KIE HTTP {response.status_code}: {msg}",
                    status=response.status_code,
                    payload=payload,
                )

            if expected_json:
                payload = self._safe_json(response)
                if payload is None:
                    raise KIEAPIError("KIE returned a non-JSON response where JSON was expected.")
                self._raise_if_api_error(payload)
            return response

        raise KIEAPIError(f"KIE request failed: {last_error or 'unknown error'}")

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _extract_error_message(payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("msg", "message", "error", "failMsg"):
                value = payload.get(key)
                if value:
                    return str(value)
        return ""

    @classmethod
    def _raise_if_api_error(cls, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        # KIE commonly uses code=200 for success. Some status responses have historically
        # returned unusual top-level codes, so only fail aggressively when an error message
        # or explicit success=false is present.
        if payload.get("success") is False:
            raise KIEAPIError(cls._extract_error_message(payload) or "KIE API returned success=false", payload=payload)
        code = payload.get("code")
        msg = str(payload.get("msg") or payload.get("message") or "").lower()
        if isinstance(code, int) and code >= 400 and msg not in {"success", "ok"}:
            # recordInfo documentation has shown unusual top-level codes alongside msg=success.
            # Treat those as transport quirks, but raise normal JSON-level API errors.
            raise KIEAPIError(cls._extract_error_message(payload) or f"KIE API code {code}", payload=payload)

    def raw_api_request(
        self,
        method: str,
        endpoint: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Call any documented KIE REST endpoint without leaking the API key off-domain."""
        method = (method or "GET").upper().strip()
        endpoint = (endpoint or "").strip()
        if not endpoint:
            raise KIEAPIError("KIE endpoint is empty.")
        if endpoint.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            parsed = urlparse(endpoint)
            allowed_hosts = {"api.kie.ai", "kieai.redpandaai.co"}
            if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
                raise KIEAPIError(
                    "For security, authenticated raw requests are restricted to KIE-owned API hosts "
                    "(api.kie.ai and kieai.redpandaai.co)."
                )
            url = endpoint
        else:
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{self.config.api_base}{endpoint}"

        kwargs: dict[str, Any] = {}
        if query:
            kwargs["params"] = query
        if body is not None and method not in {"GET", "HEAD"}:
            kwargs["json"] = body
            kwargs["headers"] = {"Content-Type": "application/json"}

        # Some KIE endpoints (notably chat/Codex-style APIs) may answer with
        # text/event-stream rather than one JSON document. Fetch the raw response
        # first, then normalize JSON, SSE, or plain text into a serializable value.
        response = self._request(method, url, expected_json=False, **kwargs)
        payload = self._safe_json(response)
        if payload is not None:
            self._raise_if_api_error(payload)
            return payload

        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in content_type or any(line.startswith("data:") for line in response.text.splitlines()):
            events: list[Any] = []
            for line in response.text.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                value = line[5:].strip()
                if not value or value == "[DONE]":
                    continue
                try:
                    events.append(json.loads(value))
                except json.JSONDecodeError:
                    events.append(value)
            return {"stream_events": events, "event_count": len(events)}

        return {"text": response.text}

    def create_task(self, model: str, input_payload: dict[str, Any], callback_url: str = "") -> str:
        body: dict[str, Any] = {"model": model, "input": input_payload}
        if callback_url.strip():
            body["callBackUrl"] = callback_url.strip()
        response = self._request(
            "POST",
            f"{self.config.api_base}/api/v1/jobs/createTask",
            headers={"Content-Type": "application/json"},
            json=body,
        )
        payload = response.json()
        task_id = ((payload.get("data") or {}).get("taskId") if isinstance(payload, dict) else None)
        if not task_id:
            raise KIEAPIError("KIE createTask response did not contain data.taskId", payload=payload)
        return str(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"{self.config.api_base}/api/v1/jobs/recordInfo",
            params={"taskId": task_id},
        )
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise KIEAPIError("KIE recordInfo response did not contain a data object", payload=payload)
        return data

    def get_remaining_credits(self) -> float:
        """Fetch the current KIE account balance from the documented Common API."""
        payload = self.raw_api_request("GET", "/api/v1/chat/credit")
        value = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise KIEAPIError("KIE credit response did not contain a numeric data balance.", payload=payload)
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise KIEAPIError("KIE credit response did not contain a numeric data balance.", payload=payload) from exc

    def wait_for_task(
        self,
        task_id: str,
        *,
        timeout_seconds: float = 900.0,
        initial_interval: float = 2.5,
        max_interval: float = 15.0,
        success_grace_seconds: float = 30.0,
    ) -> KIEResult:
        deadline = time.monotonic() + float(timeout_seconds)
        interval = max(float(initial_interval), 0.5)
        last: dict[str, Any] = {}
        success_seen_at: float | None = None

        while time.monotonic() < deadline:
            last = self.get_task(task_id)
            state = str(last.get("state") or "").lower()
            if state == "success":
                result = self.normalize_result(last)
                if result.urls:
                    return result
                # Some Market providers mark the task successful shortly before
                # resultJson/response is persisted. Keep polling for a short grace
                # period instead of turning a successful generation into a false
                # "no URL" error.
                now = time.monotonic()
                if success_seen_at is None:
                    success_seen_at = now
                if now - success_seen_at >= max(float(success_grace_seconds), 0.0):
                    return result
                time.sleep(min(interval, 2.5))
                continue
            if state == "fail":
                reason = last.get("failMsg") or last.get("failCode") or "Generation failed"
                raise KIEAPIError(f"KIE task {task_id} failed: {reason}", payload=last)
            time.sleep(interval)
            interval = min(interval * 1.45, max_interval)

        state = str(last.get("state") or "unknown")
        progress = last.get("progress")
        raise KIEAPIError(
            f"Timed out waiting for KIE task {task_id} (state={state}, progress={progress}).",
            payload=last,
        )

    @classmethod
    def normalize_result(cls, data: dict[str, Any]) -> KIEResult:
        return KIEResult(
            task_id=str(data.get("taskId") or ""),
            state=str(data.get("state") or ""),
            urls=cls.extract_result_urls(data),
            credits_consumed=float(data.get("creditsConsumed") or 0),
            raw=data,
        )

    @classmethod
    def extract_result_urls(cls, data: dict[str, Any]) -> list[str]:
        urls: list[str] = []

        def walk(obj: Any, depth: int = 0) -> None:
            if depth > 12:
                return
            if isinstance(obj, str):
                text = obj.strip()
                if text.startswith(("http://", "https://", "oss://")):
                    urls.append(text)
                    return
                # resultJson is occasionally returned as JSON inside another JSON
                # string. Decode recursively while keeping malformed text harmless.
                if text.startswith(("{", "[", '"')):
                    try:
                        decoded = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        decoded = None
                    if decoded is not None and decoded != obj:
                        walk(decoded, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item, depth + 1)
            elif isinstance(obj, dict):
                # Prefer common result fields first, then recursively inspect the remainder.
                priority = (
                    "resultJson", "response", "result", "output", "outputs",
                    "resultUrls", "resultUrl", "fullResultUrls",
                    "resultImageUrl", "resultVideoUrl", "resultAudioUrl",
                    "urls", "url", "images", "videos", "audio",
                    "imageUrls", "videoUrls", "audioUrls", "imageUrl", "videoUrl", "audioUrl",
                    "files",
                )
                seen = set()
                for key in priority:
                    if key in obj:
                        seen.add(key)
                        walk(obj[key], depth + 1)
                for key, item in obj.items():
                    # Do not mistake source media echoed in request parameters for
                    # generated output when falling back to a whole-record scan.
                    if key not in seen and key not in {"param", "paramJson", "input", "request"}:
                        walk(item, depth + 1)

        walk(data)
        # Stable de-duplication.
        return list(dict.fromkeys(urls))

    def get_credits(self) -> float:
        response = self._request("GET", f"{self.config.api_base}/api/v1/chat/credit")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, (int, float)):
            raise KIEAPIError("Unexpected credit response from KIE", payload=payload)
        return float(data)

    def get_download_url(self, generated_url: str) -> str:
        response = self._request(
            "POST",
            f"{self.config.api_base}/api/v1/common/download-url",
            headers={"Content-Type": "application/json"},
            json={"url": generated_url},
        )
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, str) or not data.startswith(("http://", "https://")):
            raise KIEAPIError("KIE did not return a valid download URL", payload=payload)
        return data

    def upload_file(self, file_path: str, upload_path: str = "comfyui/uploads") -> str:
        name = os.path.basename(file_path)
        with open(file_path, "rb") as handle:
            response = self._request(
                "POST",
                f"{self.config.upload_base}/api/file-stream-upload",
                files={"file": (name, handle)},
                data={"uploadPath": upload_path, "fileName": name},
            )
        return self._extract_upload_url(response.json())

    def upload_bytes(
        self,
        content: bytes,
        *,
        filename: str,
        mime_type: str = "application/octet-stream",
        upload_path: str = "comfyui/uploads",
    ) -> str:
        # Multipart stream avoids base64 overhead and works for both small and large files.
        response = self._request(
            "POST",
            f"{self.config.upload_base}/api/file-stream-upload",
            files={"file": (filename, content, mime_type)},
            data={"uploadPath": upload_path, "fileName": filename},
        )
        return self._extract_upload_url(response.json())

    @staticmethod
    def _extract_upload_url(payload: Any) -> str:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            for key in ("downloadUrl", "fileUrl", "url"):
                value = data.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
        raise KIEAPIError("KIE upload response did not contain a usable URL", payload=payload)

    def download_bytes(self, url: str) -> bytes:
        # Generated URLs are usually directly downloadable and do not require auth.
        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            if response.ok:
                return response.content
        except requests.RequestException:
            pass

        # KIE can convert its generated URLs into a short-lived direct download URL.
        direct = self.get_download_url(url)
        response = self.session.get(direct, timeout=self.config.request_timeout)
        if not response.ok:
            raise KIEAPIError(f"Failed downloading generated media: HTTP {response.status_code}")
        return response.content


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)

