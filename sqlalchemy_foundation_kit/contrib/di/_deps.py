"""Shared dishka dependency helpers.

Centralizes the dishka import boilerplate and availability check so each
provider module doesn't have to repeat it.
"""

from __future__ import annotations

try:
    from dishka import Provider, Scope, provide

    HAS_DISHKA = True
except ImportError:
    HAS_DISHKA = False
    Provider = object  # type: ignore[misc,assignment]
    Scope = None  # type: ignore[misc,assignment]
    provide = None  # type: ignore[misc,assignment]


def check_dishka() -> None:
    """Raise ImportError if dishka is not installed.

    Raises:
        ImportError: If dishka is not available.
    """
    if not HAS_DISHKA:
        raise ImportError(
            "dishka is required for providers. Install it with: pip install 'sqlalchemy-foundation-kit[dishka]'"
        )


__all__ = ["HAS_DISHKA", "Provider", "Scope", "check_dishka", "provide"]
