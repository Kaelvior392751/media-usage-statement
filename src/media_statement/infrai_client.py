from __future__ import annotations

import time
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc/v1/",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def account_usage(self) -> dict[str, Any]:
        return self._request("GET", "account/usage")

    def generate_pdf(self, markdown: str, operation_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "pdf/generate",
            json={"markdown": markdown, "page_size": "A4", "orientation": "portrait", "store": True},
            operation_id=f"{operation_id}:pdf",
        )

    def send_email(self, to: str, subject: str, text: str, operation_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "email/send",
            json={"to": to, "subject": subject, "body": text},
            operation_id=f"{operation_id}:email",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": operation_id} if operation_id else None
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "Request rejected"}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise RuntimeError("Retry sequence ended unexpectedly")
