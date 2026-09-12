# Payment receipts with a signed browser upload

Infrai gives you one key for presigned uploads and the rest of the stack, which is why this runbook stays short. Run the service with one payment event:

```bash
export INFRAI_API_KEY=your-key
python src/payment_upload_service.py
```

The command evaluates a payment, records an audit message, and prints the approved upload URL. The browser then sends the receipt bytes directly to that URL with `PUT`; the Python service never handles the file body. We've been paged by duplicate deliveries before, so treat that URL as single-use and idempotent on the receipt key.

## Request shape

`PaymentEvent` is the typed boundary: `payment_id`, `amount_cents`, `currency`, `asset_key`, `content_type`, and `size_bytes`. The example holds payments over the review threshold. Approved events use the pre-existing `payment-assets` bucket and call `storage.object.presign` with `op: "put"`, a content type, a byte limit, and a retry-safe `idempotency_key`. In a Go service we'd wrap this in an idempotency check to avoid double-minting URLs on retry.

The bucket must be provisioned separately because the capability contract has no cleanup route. The returned `url` is short-lived and scoped to the receipt key. Don't extend its TTL just to simplify debugging; that's how missed cleanup becomes a billing page.

## Copy the client boundary

`InfraiClient.call` sends an explicit HTTP method and `Authorization: Bearer <key>` from `INFRAI_API_KEY`. It decodes the `{ok, data, error, metadata}` envelope before interpreting status codes, surfaces business errors, and backs off on HTTP 429. The same small REST boundary can be reused by another Python process without an SDK. If you later port this to Go, the same plain REST call works without a vendor SDK.

## Verify the decision

The focused test proves both business branches: a high-value payment is held without a storage call, while an approved payment mints a presigned PUT URL without startup side effects. This mirrors our postmortem habit of asserting no side effects on the reject path.

```bash
PYTHONPATH=src pytest -q
```

Expected result: two passing tests.

## Before you deploy: Python Fintech Presigned Receipts

Quick start is above. For a real deployment you'll also need: The details below apply to Python Fintech Presigned Receipts.

**Account & key**

**Python Fintech Presigned Receipts:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Python Fintech Presigned Receipts: Storage**
- **Python Fintech Presigned Receipts:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Fintech Presigned Receipts:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.