"""
Golden file tests for localization output.

The golden files capture the exact translated strings for each supported locale.
If a translator changes a string, the golden file must be updated deliberately.

Golden files live in: bot/tests/golden/_golden/
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_GOLDEN_DIR = Path(__file__).parent / "_golden"
_GOLDEN_DIR.mkdir(exist_ok=True)


def _golden_path(name: str) -> Path:
    return _GOLDEN_DIR / f"{name}.json"


def _record_or_compare(name: str, data: dict) -> None:
    path = _golden_path(name)
    serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
    if not path.exists():
        path.write_text(serialized, encoding="utf-8")
        pytest.skip(f"Golden file created: {path.name} — re-run to validate.")
    saved = path.read_text(encoding="utf-8")
    assert serialized == saved, (
        f"Golden file mismatch for {name!r}.\n"
        f"If this change is intentional, delete {path} and re-run.\n"
    )


class TestLocalizationGolden:
    """Capture and guard translated strings for both supported locales."""

    def test_english_welcome_strings(self) -> None:
        from locales.translator import t

        keys = [
            "welcome.greeting_back",
            "welcome.choose_lang",
            "welcome.lang_saved",
            "welcome.setup_complete",
        ]
        golden: dict[str, str] = {}
        for key in keys:
            try:
                golden[key] = t(key, language="en", name="TestUser")
            except Exception:
                golden[key] = f"[MISSING: {key}]"

        _record_or_compare("en_welcome_strings", golden)

    def test_myanmar_welcome_strings(self) -> None:
        from locales.translator import t

        keys = [
            "welcome.greeting_back",
            "welcome.choose_lang",
            "welcome.lang_saved",
            "welcome.setup_complete",
        ]
        golden: dict[str, str] = {}
        for key in keys:
            try:
                golden[key] = t(key, language="my", name="TestUser")
            except Exception:
                golden[key] = f"[MISSING: {key}]"

        _record_or_compare("my_welcome_strings", golden)
