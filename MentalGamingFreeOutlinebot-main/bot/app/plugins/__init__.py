"""Plugin foundation; no feature plugins are enabled by default."""

from .base_plugin import BasePlugin, PluginManifest, PluginStatus
from .plugin_loader import PluginLoader
from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry

__all__ = [
    "BasePlugin",
    "PluginManifest",
    "PluginStatus",
    "PluginLoader",
    "PluginManager",
    "PluginRegistry",
]