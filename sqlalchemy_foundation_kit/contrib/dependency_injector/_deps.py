"""Shared dependency-injector dependency helpers.

Centralizes the dependency-injector import boilerplate and availability check so each
module doesn't have to repeat it.
"""

from __future__ import annotations

from typing import Any, NoReturn


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


class _MissingDependencyInjector:
    """Stand-in for a dependency-injector name, raising the intended ImportError on first use.

    ``BaseDIContainer`` subclasses ``containers.DeclarativeContainer`` and the container
    modules build ``providers.*`` in their class bodies, which runs before any check a
    base class could perform. Without this, importing them without dependency-injector
    installed fails with ``AttributeError: 'NoneType' object has no attribute
    'DeclarativeContainer'`` instead of the message that says what to install.
    """

    def __getattr__(self, name: str) -> NoReturn:
        check_dependency_injector()
        raise AttributeError(name)  # pragma: no cover - unreachable, check raises

    def __call__(self, *args: Any, **kwargs: Any) -> NoReturn:
        check_dependency_injector()
        raise TypeError("dependency-injector is not installed")  # pragma: no cover - unreachable


try:
    from dependency_injector import containers, providers

    HAS_DEPENDENCY_INJECTOR = True
except ImportError:
    HAS_DEPENDENCY_INJECTOR = False
    containers = _MissingDependencyInjector()  # type: ignore[misc,assignment]
    providers = _MissingDependencyInjector()  # type: ignore[misc,assignment]


__all__ = [
    "HAS_DEPENDENCY_INJECTOR",
    "check_dependency_injector",
    "containers",
    "providers",
]
