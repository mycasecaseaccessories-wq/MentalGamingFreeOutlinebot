from __future__ import annotations

import string

from locales.en import TRANSLATIONS as EN
from locales.my import TRANSLATIONS as MY
from locales.translator import t


REFERRAL_PREFIXES = ("referral.", "admin.referrals.")


def _keys() -> set[str]:
    return {key for key in EN | MY if key.startswith(REFERRAL_PREFIXES)}


def _placeholders(value: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(value) if field}


def test_referral_keys_are_complete_in_en_and_my() -> None:
    keys = _keys()
    assert keys
    assert keys <= EN.keys()
    assert keys <= MY.keys()


def test_referral_placeholders_match_between_languages() -> None:
    for key in _keys():
        assert _placeholders(EN[key]) == _placeholders(MY[key]), key


def test_required_customer_and_admin_referral_keys_resolve() -> None:
    required = {
        "menu.refer_friends",
        "referral.invite_title",
        "referral.invite_body",
        "referral.share_link",
        "referral.my_referrals",
        "referral.history_title",
        "referral.no_referrals",
        "referral.pending",
        "referral.qualified",
        "referral.rewarded",
        "referral.invalid",
        "referral.invalid_link",
        "referral.already_registered",
        "referral.self_referral",
        "referral.disabled",
        "referral.generic_error",
        "admin.referrals.menu",
        "admin.referrals.enabled",
        "admin.referrals.disabled",
        "admin.referrals.stats",
        "admin.referrals.recent",
        "admin.referrals.invalidated",
        "admin.referrals.total",
        "admin.referrals.pending",
        "admin.referrals.qualified",
        "admin.referrals.rewarded",
        "admin.referrals.invalid",
        "admin.referrals.source_personal_link",
        "admin.referrals.source_start_payload",
    }
    for language in ("en", "my"):
        for key in required:
            assert t(key, language=language) != key, (language, key)


def test_dynamic_referral_messages_preserve_placeholders() -> None:
    for language in ("en", "my"):
        text = t(
            "referral.invite_body",
            language=language,
            token="ABC123",
            link="https://t.me/example?start=ref_ABC123",
            total=3,
            pending=2,
            qualified=1,
        )
        assert "ABC123" in text
        assert "3" in text
        assert "2" in text
        assert "1" in text

        invalidated = t("admin.referrals.invalidated", language=language, referral="REF-ABC")
        assert "REF-ABC" in invalidated
