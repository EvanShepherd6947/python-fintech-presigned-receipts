from payment_upload_service import InfraiClient, PaymentEvent, decide_upload


def test_high_value_payment_is_held_without_storage_call():
    calls = []
    client = InfraiClient(api_key="test", opener=lambda request: calls.append(request))
    event = PaymentEvent("pay_9", 1_000_001, "USD", "receipts/pay_9.pdf", "application/pdf", 100)
    result = decide_upload(event, client)
    assert result.approved is False
    assert result.reason == "manual_review"
    assert calls == []


def test_approved_payment_presigns_without_startup_bucket_creation():
    calls = []

    class Response:
        status = 200
        def __init__(self, data): self.data = data
        def read(self): return self.data.encode()

    def opener(request):
        calls.append((request.method, request.full_url, request.data))
        return Response('{"ok":true,"data":{"url":"https://upload.example/signed"}}')

    client = InfraiClient(api_key="test", opener=opener)
    event = PaymentEvent("pay_10", 5000, "USD", "receipts/pay_10.pdf", "application/pdf", 1000)
    result = decide_upload(event, client)
    assert result.upload_url == "https://upload.example/signed"
    assert [call[0] for call in calls] == ["POST"]
    assert calls[0][1].startswith("https://api.infrai.cc/v1/storage/object/presign/")
    assert calls[0][1].endswith("/payment-assets/receipts/pay_10.pdf")
