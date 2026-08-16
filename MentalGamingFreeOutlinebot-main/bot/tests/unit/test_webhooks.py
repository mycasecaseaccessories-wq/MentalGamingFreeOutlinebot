from app.webhooks import sign_payload, verify_signature


def test_webhook_signature_round_trip() -> None:
    payload = b'{"event":"test"}'
    signature = sign_payload(payload, "secret")
    assert verify_signature(payload, "secret", signature)
    assert not verify_signature(payload + b"x", "secret", signature)
