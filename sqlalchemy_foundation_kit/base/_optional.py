"""Utilities for handling optional dependencies."""

from __future__ import annotations

import importlib
import types


def require_optional(module_name: str, extra_name: str) -> types.ModuleType:
    """Import an optional dependency or raise a helpful error.

    Args:
        module_name: Name of the module to import (e.g., "orjson", "opentelemetry").
        extra_name: Name of the pip extra that provides this dependency (e.g., "json", "telemetry").

    Returns:
        The imported module.

    Raises:
        ImportError: If the module is not installed, with installation instructions.

    Examples:
        >>> orjson = require_optional("orjson", "json")
        >>> from opentelemetry import trace
        # or
        >>> otel = require_optional("opentelemetry", "telemetry")
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(
            f"{module_name} is required for this functionality. "
            f"Install it with: pip install 'sqlalchemy-foundation-kit[{extra_name}]'"
        ) from e


__all__ = ["require_optional"]
