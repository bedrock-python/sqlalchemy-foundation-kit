"""Base dependency-injector container with automatic dependency checking."""

from __future__ import annotations

from ._deps import check_dependency_injector, containers


class BaseDIContainer(containers.DeclarativeContainer):  # type: ignore[misc,name-defined]
    """Base container that checks dependency-injector availability on subclass creation.

    All dependency-injector containers should inherit from this class instead of directly
    from containers.DeclarativeContainer. This ensures consistent error messages when
    dependency-injector is not installed.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Check dependency-injector availability when creating a subclass."""
        super().__init_subclass__(**kwargs)
        check_dependency_injector()

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Check dependency-injector availability when instantiating."""
        check_dependency_injector()
        super().__init__(*args, **kwargs)


__all__ = ["BaseDIContainer"]
