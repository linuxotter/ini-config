"""
Parser for INI configuration files.

This module extends the functionality of the built-in `configparser` module.
It allows defining expected configuration structures, setting default values
for optional parameters, and provides access to parsed data via a Namespace
object.
"""

import importlib.metadata
from .ini_config import IniConfig, ConfigError, ConfigNamespace

__all__ = ["IniConfig", "ConfigError", "ConfigNamespace"]

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"
