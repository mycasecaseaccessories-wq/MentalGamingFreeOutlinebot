"""
Localisation (i18n) package.

Provides translated UI strings for all supported languages.

Supported languages:
  en — English   (default)
  my — Myanmar (Burmese)

Usage:
    from locales import t
    message = t("welcome.greeting", language="my")

Architecture:
  • Each language is a module (locales/en.py, locales/my.py) containing
    a flat dict of translation keys → string values.
  • The Translator class in locales/translator.py resolves keys,
    falls back to English when a key is missing in the target language,
    and supports %s / %(name)s format placeholders.

Adding a new language:
  1. Create locales/<code>.py with the TRANSLATIONS dict.
  2. Register it in locales/translator.py LANGUAGE_REGISTRY.
  3. Add the code to the Language enum in app/models/enums.py.
"""

from .translator import Translator, t

__all__ = ["Translator", "t"]
