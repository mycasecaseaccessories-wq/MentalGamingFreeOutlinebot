"""
LanguageService — multilingual translation management.

Responsibilities:
  • Load and cache translation modules for all supported languages.
  • Provide a translate() helper that falls back to English.
  • Persist per-user language preferences via UserService.
  • Support runtime reload of translations (useful for hot-patching).

Architecture:
  Translation strings live in locales/<code>/__init__.py as flat dicts.
  LanguageService wraps the lower-level t() function from locales.translator
  and adds user-preference management.

Usage:
    svc = LanguageService(db)

    # Translate with a known language code
    text = svc.translate("welcome.greeting", "my", name="Alice")

    # Change a user's language and persist it
    await svc.set_language(telegram_id=12345, language_code="my")

    # Get the stored language for a user
    lang = await svc.get_language(12345)   # → "my"

Phase 0.4: Full implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from database.connection import DatabaseManager
from locales.translator import t, _get_registry, _LANGUAGE_REGISTRY

from .base import BaseService

logger = logging.getLogger(__name__)

# Languages supported by the platform.
SUPPORTED_LANGUAGES: list[str] = ["en", "my"]
DEFAULT_LANGUAGE: str = "en"


class LanguageService(BaseService):
    """
    Manages multilingual translation and per-user language preferences.

    The service caches translation modules in memory.  Call reload() to
    flush and rebuild the cache (e.g. after hot-swapping locale files).
    """

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        super().__init__(db)
        # Per-process in-memory cache: telegram_id → language code.
        # Avoids a DB lookup on every translated message.
        self._user_lang_cache: dict[int, str] = {}

    # ── Translation ───────────────────────────────────────────────────────

    def translate(self, key: str, language: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
        """
        Return the translated string for *key* in *language*.

        Falls back to English when the key is missing in *language*.
        Returns the key itself as a last resort (logged as a warning).

        Args:
            key:      Dot-notation translation key (e.g. 'welcome.greeting').
            language: Two-letter language code ('en' or 'my').
            **kwargs: Format placeholders passed to str.format_map().

        Returns:
            Translated (and formatted) string.
        """
        if language not in SUPPORTED_LANGUAGES:
            logger.warning(
                "Unsupported language %r — falling back to %s", language, DEFAULT_LANGUAGE
            )
            language = DEFAULT_LANGUAGE
        return t(key, language=language, **kwargs)

    def load_language(self, language_code: str) -> dict[str, str]:
        """
        Return the translation dict for *language_code*.

        Triggers lazy loading of the registry on first call.

        Args:
            language_code: Two-letter language code ('en' or 'my').

        Returns:
            Dict mapping translation keys to localised strings.

        Raises:
            KeyError: If the language is not registered.
        """
        registry = _get_registry()
        if language_code not in registry:
            raise KeyError(
                f"Language {language_code!r} is not registered. "
                f"Available: {list(registry.keys())}"
            )
        return registry[language_code]

    def reload(self) -> None:
        """
        Flush the in-memory translation registry and rebuild it.

        Use this after hot-patching locale files at runtime.
        Also clears the per-user language cache so stale preferences
        are re-fetched from the database on next access.
        """
        global _LANGUAGE_REGISTRY
        import locales.translator as _translator_mod
        _translator_mod._LANGUAGE_REGISTRY = None  # force reload
        self._user_lang_cache.clear()
        logger.info("Translation registry reloaded.")

    # ── User language preference ──────────────────────────────────────────

    async def set_language(self, telegram_id: int, language_code: str) -> None:
        """
        Persist the user's preferred language to the database.

        Updates the in-memory cache so subsequent translate() calls
        use the new language without an extra DB round-trip.

        Args:
            telegram_id:   Telegram user ID.
            language_code: Language code to store ('en' or 'my').

        Raises:
            ValueError: If language_code is not in SUPPORTED_LANGUAGES.
        """
        if language_code not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language {language_code!r}. "
                f"Supported: {SUPPORTED_LANGUAGES}"
            )
        from database.repositories import UserRepository
        async with self.db.session() as session:
            repo = UserRepository(session)
            await repo.update_language(telegram_id, language_code)
        self._user_lang_cache[telegram_id] = language_code
        logger.debug(
            "Language preference saved — telegram_id=%s language=%s",
            telegram_id, language_code,
        )

    async def get_language(self, telegram_id: int) -> str:
        """
        Return the stored language code for a user.

        Checks the in-memory cache first, then falls back to the database.
        Returns DEFAULT_LANGUAGE when the user has no preference stored.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            Two-letter language code.
        """
        if telegram_id in self._user_lang_cache:
            return self._user_lang_cache[telegram_id]

        from database.repositories import UserRepository
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.get_by_telegram_id(telegram_id)

        lang = row.language if row and row.language else DEFAULT_LANGUAGE
        self._user_lang_cache[telegram_id] = lang
        return lang

    def get_cached_language(self, telegram_id: int) -> str:
        """
        Return the cached language for a user without a DB lookup.

        Returns DEFAULT_LANGUAGE when the user is not in cache.
        Use this inside hot paths (e.g. middleware) where the language
        has already been loaded once in the request lifecycle.
        """
        return self._user_lang_cache.get(telegram_id, DEFAULT_LANGUAGE)

    def cache_language(self, telegram_id: int, language_code: str) -> None:
        """
        Store a language code in the in-memory cache.

        Called by the language middleware after resolving the user's language
        so that subsequent calls within the same update use the cache.

        Args:
            telegram_id:   Telegram user ID.
            language_code: Language code to cache.
        """
        self._user_lang_cache[telegram_id] = language_code
