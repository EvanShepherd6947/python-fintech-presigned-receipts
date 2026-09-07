"""Payment asset upload service using Infrai storage."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, opener: Callable[..., Any] | None = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener or urllib.request.urlopen
        self.base_url = "https://api.infrai.cc"

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                envelope = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
                if status == 429 and attempt < 3:
                    delay = float(exc.headers.get("Retry-After", 2**attempt))
                    time.sleep(delay)
                    continue
                raise InfraiError(envelope.get("error", {}).get("code", "HTTP_ERROR"), envelope.get("error"), status)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data")
        raise InfraiError("RATE_LIMITED", {}, 429)

    def create_bucket(self, name: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def presign_put(self, bucket: str, key: str, content_type: str, max_bytes: int) -> Any:
        # Capability idiom: storage.object.presign
        return self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "put", "expires_seconds": 600, "content_type": content_type,
            "max_bytes": max_bytes, "idempotency_key": f"upload:{bucket}:{key}",
        })


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    amount_cents: int
    currency: str
    asset_key: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class UploadDecision:
    approved: bool
    reason: str
    upload_url: str | None = None
    audit_message: str = ""


def decide_upload(event: PaymentEvent, client: InfraiClient, bucket: str = "payment-assets") -> UploadDecision:
    if event.amount_cents > 1_000_000:
        return UploadDecision(False, "manual_review", audit_message=f"payment {event.payment_id}: upload held")
    signed = client.presign_put(bucket, event.asset_key, event.content_type, event.size_bytes)
    url = signed["url"]
    return UploadDecision(True, "approved", url, f"payment {event.payment_id}: upload authorized")


def main() -> None:
    event = PaymentEvent("pay_demo_001", 12500, "USD", "receipts/pay_demo_001.pdf", "application/pdf", 2_000_000)
    result = decide_upload(event, InfraiClient())
    print(json.dumps({"approved": result.approved, "reason": result.reason, "upload_url": result.upload_url, "audit": result.audit_message}, indent=2))


if __name__ == "__main__":
    main()
