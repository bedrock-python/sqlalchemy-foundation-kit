"""Shared dependency-injector dependency helpers.

Centralizes the dependency-injector import boilerplate and availability check so each
module doesn't have to repeat it.
"""

from __future__ import annotations

try:
    from dependency_injector import containers, providers

    HAS_DEPENDENCY_INJECTOR = True
except ImportError:
    HAS_DEPENDENCY_INJECTOR = False
    containers = None  # type: ignore[misc,assignment]
    providers = None  # type: ignore[misc,assignment]


def check_dependency_injector() -> None:
    """Raise ImportError if dependency-injector is not installed.

    Raises:
        ImportError: If dependency-injector is not available.
    """
    if not HAS_DEPENDENCY_INJECTOR:
        raise ImportError(
            "dependency-injector is required for containers. "
            "Install it with: pip install 'sqlalchemy-foundation-kit[dependency-injector]'"
        )


__all__ = ["HAS_DEPENDENCY_INJECTOR", "check_dependency_injector", "containers", "providers"]
