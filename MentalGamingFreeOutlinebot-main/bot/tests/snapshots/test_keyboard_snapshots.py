"""
Snapshot tests for keyboard layouts.

These tests assert that keyboard structures remain stable across refactors.
Update the snapshots intentionally when keyboard layouts are changed by design.

Usage: Run normally — if a snapshot file doesn't exist yet it is created on
the first run. Subsequent runs compare against the saved snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SNAPSHOT_DIR = Path(__file__).parent / "_snapshots"
_SNAPSHOT_DIR.mkdir(exist_ok=True)


def _snapshot_path(name: str) -> Path:
    return _SNAPSHOT_DIR / f"{name}.json"


def _assert_snapshot(name: str, data: object) -> None:
    """
    Compare *data* against a saved snapshot file.

    On first run (no snapshot file), creates the file and passes.
    On subsequent runs, compares against the saved value.
    """
    path = _snapshot_path(name)
    serialized = json.dumps(data, sort_keys=True, indent=2, default=str)
    if not path.exists():
        path.write_text(serialized, encoding="utf-8")
        pytest.skip(f"Snapshot created: {path.name} — re-run to validate.")
    saved = path.read_text(encoding="utf-8")
    assert serialized == saved, (
        f"Snapshot mismatch for {name!r}.\n"
        f"To update: delete {path} and re-run the test.\n"
        f"Expected:\n{saved}\n\nGot:\n{serialized}"
    )


class TestLanguageSelectionKeyboard:
    def test_language_keyboard_structure(self) -> None:
        """The language selection keyboard layout must be stable."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="set_lang:my")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")],
        ])

        structure = [
            [{"text": btn.text, "callback_data": btn.callback_data} for btn in row]
            for row in keyboard.inline_keyboard
        ]
        _assert_snapshot("language_selection_keyboard", structure)


class TestMessageOutputSnapshots:
    def test_welcome_message_keys_exist(self) -> None:
        """Ensure the localization keys used in start.py are present in both locales."""
        from locales.translator import t

        required_keys = [
            "welcome.greeting_back",
            "welcome.choose_lang",
            "welcome.lang_saved",
            "welcome.setup_complete",
            "placeholder.coming_soon",
        ]
        for lang in ("en", "my"):
            for key in required_keys:
                try:
                    result = t(key, language=lang, name="Test")
                    assert result, f"Key {key!r} returned empty for lang={lang!r}"
                except Exception as exc:
                    pytest.fail(f"t({key!r}, language={lang!r}) raised: {exc}")
