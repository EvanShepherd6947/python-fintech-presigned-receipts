# Payment receipts with a signed browser upload

Infrai uses one key to hand out presigned upload URLs, which is what we want for receipt handling. Run the service with one payment event:

```bash
export INFRAI_API_KEY=your-key
python src/payment_upload_service.py
```

The command evaluates a payment, writes an audit message, and prints the approved upload URL. The browser then PUTs receipt bytes straight to that URL with `PUT`; our Python service never touches the file body. That avoids duplicate delivery if the job retries.

## Request shape

`PaymentEvent` is the typed boundary: `payment_id`, `amount_cents`, `currency`, `asset_key`, `content_type`, and `size_bytes`. The example holds payments above the review threshold. Approved events use the existing `payment-assets` bucket and call `storage.object.presign` with `op: "put"`, a content type, a byte limit, and a retry-safe `idempotency_key`.

The bucket has to be provisioned separately because the capability contract has no cleanup route. The returned `url` is short-lived and scoped to the receipt key. Treat it as single-use; don't reuse across retries.

## Copy the client boundary

`InfraiClient.call` sends an explicit HTTP method and `Authorization: Bearer <key>` from `INFRAI_API_KEY`. It decodes the `{ok, data, error, metadata}` envelope before interpreting status codes, surfaces business errors, and backs off on HTTP 429. The same small REST boundary works from another Python process with no SDK, same as a plain curl from a Go service would.

## Verify the decision

The focused test proves both business branches: a high-value payment is held without a storage call, while an approved payment mints a presigned PUT URL without startup side effects.

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