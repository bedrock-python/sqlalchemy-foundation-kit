"""Shared dishka dependency helpers.

Centralizes the dishka import boilerplate and availability check so each
provider module doesn't have to repeat it.
"""

from __future__ import annotations

from typing import Any, NoReturn


def check_dishka() -> None:
    """Raise ImportError if dishka is not installed.

    Raises:
        ImportError: If dishka is not available.
    """
    if not HAS_DISHKA:
        raise ImportError(
            "dishka is required for providers. Install it with: pip install 'sqlalchemy-foundation-kit[dishka]'"
        )


class _MissingDishka:
    """Stand-in for a dishka name, raising the intended ImportError on first use.

    Provider modules read ``Scope.APP`` and apply ``@provide`` in their class bodies,
    which runs before any check a base class could perform. Without this, importing
    them without dishka installed fails with ``AttributeError: 'NoneType' object has
    no attribute 'APP'`` instead of the message that says what to install.
    """

    def __getattr__(self, name: str) -> NoReturn:
        check_dishka()
        raise AttributeError(name)  # pragma: no cover - unreachable, check_dishka raises

    def __call__(self, *args: Any, **kwargs: Any) -> NoReturn:
        check_dishka()
        raise TypeError("dishka is not installed")  # pragma: no cover - unreachable


try:
    from dishka import Provider, Scope, provide

    HAS_DISHKA = True
except ImportError:
    HAS_DISHKA = False
    Provider = object  # type: ignore[misc,assignment]
    Scope = _MissingDishka()  # type: ignore[misc,assignment]
    provide = _MissingDishka()  # type: ignore[misc,assignment]


__all__ = ["HAS_DISHKA", "Provider", "Scope", "check_dishka", "provide"]
