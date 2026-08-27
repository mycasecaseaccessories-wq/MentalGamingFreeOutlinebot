from pathlib import Path

from app.keyboards.admin_payment_review import (
    admin_approval_confirmation_keyboard,
    admin_rejection_confirmation_keyboard,
)

ROOT = Path(__file__).resolve().parents[1]


def test_unsigned_payment_confirmation_callbacks_are_not_registered() -> None:
    source = (ROOT / "app" / "handlers" / "admin.py").read_text(encoding="utf-8")
    assert 'parts[2] == "approve_confirm"' not in source
    assert 'parts[2] == "reject_confirm"' not in source
    assert "approve_confirm" not in source
    assert "reject_confirm" not in source


def test_confirmation_keyboard_fails_closed_without_signed_callback() -> None:
    approval = admin_approval_confirmation_keyboard("PAY-1", "en")
    rejection = admin_rejection_confirmation_keyboard("PAY-1", "en")
    assert approval.inline_keyboard[0][0].callback_data == "cb2:invalid"
    assert rejection.inline_keyboard[0][0].callback_data == "cb2:invalid"


def test_financial_callback_path_consumes_signed_callback_before_settlement() -> None:
    source = (ROOT / "app" / "handlers" / "admin.py").read_text(encoding="utf-8")
    consume_at = source.index("consumed = await callback_security.consume(")
    approve_at = source.index("result = await service.approve(")
    reject_at = source.index("result = await service.reject(")
    assert consume_at < approve_at
    assert consume_at < reject_at


def test_custom_rejection_reason_uses_centralized_permission_service() -> None:
    source = (ROOT / "app" / "handlers" / "admin.py").read_text(encoding="utf-8")
    custom_reason_at = source.index("async def admin_review_text")
    custom_reason = source[custom_reason_at:]
    assert "AdminAuthorizationService" in source
    assert 'has_permission_for_user(actor_user_id, "manage_payments")' in custom_reason
    assert 'getattr(user, "role", None) != "admin"' not in custom_reason
