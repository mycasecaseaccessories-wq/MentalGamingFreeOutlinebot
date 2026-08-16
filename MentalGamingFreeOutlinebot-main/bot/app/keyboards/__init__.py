"""
Keyboards package.

Contains builders for Telegram inline and reply keyboards.
Each module groups keyboards by feature domain.

Rules:
  • Keyboard builders are pure functions — they take data, return markup objects.
  • No business logic here; just layout definitions.
  • Import keyboard builders in handlers; never in services or repositories.
"""

from .main_menu import build_main_menu, build_language_selector

__all__ = ["build_main_menu", "build_language_selector"]
