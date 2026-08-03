"""
Configuration package.

Exports:
    settings         — global Settings object loaded from environment variables.
    FeatureFlags     — feature-flag key constants.
    FEATURE_FLAG_DEFAULTS — default values for all feature flags.
    SettingCategory  — category slug constants for grouping settings.
    SettingKeys      — setting key constants for all non-flag settings.
    DEFAULT_SETTINGS — list of default setting definitions.
"""

from .settings import settings
from .feature_flags import FeatureFlags, FEATURE_FLAG_DEFAULTS
from .defaults import SettingCategory, SettingKeys, DEFAULT_SETTINGS

__all__ = [
    "settings",
    "FeatureFlags",
    "FEATURE_FLAG_DEFAULTS",
    "SettingCategory",
    "SettingKeys",
    "DEFAULT_SETTINGS",
]
