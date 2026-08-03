"""
Translation engine.

Resolves i18n keys to localised strings with English fallback.

Usage:
    from locales import t

    # Simple lookup
    msg = t("common.loading", language="my")

    # With format placeholders
    msg = t("user.welcome", language="en", name="Alice")
    # → "Welcome, Alice!"
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Import language modules lazily to avoid circular imports.
# Keys follow dot-notation: "section.key" (e.g. "common.loading").
def _load_languages() -> dict[str, dict[str, str]]:
    from . import en, my  # noqa: PLC0415
    return {
        "en": en.TRANSLATIONS,
        "my": my.TRANSLATIONS,
    }


# Populated on first call to t() to allow circular-import-safe loading.
_LANGUAGE_REGISTRY: dict[str, dict[str, str]] | None = None

_FALLBACK_LANGUAGE = "en"


def _get_registry() -> dict[str, dict[str, str]]:
    global _LANGUAGE_REGISTRY
    if _LANGUAGE_REGISTRY is None:
        _LANGUAGE_REGISTRY = _load_languages()
    return _LANGUAGE_REGISTRY


class Translator:
    """
    Stateful translator bound to a specific language.

    Useful when a handler knows the user's language upfront and wants
    to avoid passing it on every call.

    Example:
        tr = Translator("my")
        msg = tr.get("common.loading")
    """

    def __init__(self, language: str) -> None:
        self.language = language

    def get(self, key: str, **kwargs: Any) -> str:
        """Translate key with optional format placeholders."""
        return t(key, language=self.language, **kwargs)


def t(key: str, language: str = _FALLBACK_LANGUAGE, **kwargs: Any) -> str:
    """
    Translate a dot-notation key to the target language.

    Falls back to English when:
      • The requested language is not registered.
      • The key is missing in the target language's translations.

    Args:
        key:      Dot-notation translation key, e.g. "common.loading".
        language: Two-letter language code, e.g. "en" or "my".
        **kwargs: Format placeholders passed to str.format_map().

    Returns:
        Translated (and formatted) string, or the key itself as last resort.

    Raises:
        Never — missing translations produce a warning log and return key.
    """
    registry = _get_registry()
    translations = registry.get(language) or registry.get(_FALLBACK_LANGUAGE, {})
    text = translations.get(key)

    if text is None:
        # Try fallback language.
        fallback = registry.get(_FALLBACK_LANGUAGE, {})
        text = fallback.get(key)
        if text is None:
            logger.warning("Missing translation — key=%r language=%s", key, language)
            return key

    if kwargs:
        try:
            return text.format_map(kwargs)
        except (KeyError, ValueError) as exc:
            logger.warning(
                "Translation format error — key=%r error=%s", key, exc
            )
            return text

    return text
