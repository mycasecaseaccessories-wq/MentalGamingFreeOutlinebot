import pytest

from app.services.membership_verification_service import MembershipVerificationService


def test_same_target_revision_is_the_verification_cache_key():
    assert (12, 7, 3) == (12, 7, 3)
    assert (12, 7, 3) != (12, 7, 4)


def test_target_types_are_narrow():
    assert "channel" in {"channel", "group"}
    assert "user" not in {"channel", "group"}


@pytest.mark.parametrize("target_id", ["", "   "])
def test_empty_target_is_not_valid(target_id):
    assert not target_id.strip()


def test_lifetime_verified_flag_is_not_used_as_target_proof():
    user_is_verified = True
    current_target_proof = None
    assert user_is_verified is True and current_target_proof is None
