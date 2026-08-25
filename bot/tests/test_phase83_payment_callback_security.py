from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_payment_confirmation_callbacks_are_fail_closed() -> None:
    source = (ROOT / "app" / "handlers" / "admin.py").read_text(encoding="utf-8")
    approve_start = source.index('if len(parts) == 4 and parts[2] == "approve_confirm"')
    reject_start = source.index('if len(parts) == 4 and parts[2] == "reject_confirm"')
    approve_block = source[approve_start:reject_start]
    reject_block = source[reject_start:]
    assert "service.approve(" not in approve_block
    assert "service.reject(" not in reject_block
    assert "invalid_state" in approve_block
    assert "invalid_state" in reject_block


def test_financial_callback_path_consumes_signed_callback_before_settlement() -> None:
    source = (ROOT / "app" / "handlers" / "admin.py").read_text(encoding="utf-8")
    consume_at = source.index("consumed = await callback_security.consume(")
    approve_at = source.index("result = await service.approve(")
    reject_at = source.index("result = await service.reject(")
    assert consume_at < approve_at
    assert consume_at < reject_at
