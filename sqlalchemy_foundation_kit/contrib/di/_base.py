"""Base Dishka provider with automatic dependency checking."""

from __future__ import annotations

from ._deps import Provider, check_dishka


class BaseDishkaProvider(Provider):
    """Base provider that checks dishka availability on subclass creation.

    All Dishka providers should inherit from this class instead of directly
    from dishka.Provider. This ensures consistent error messages when dishka
    is not installed.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Check dishka availability when creating a subclass."""
        super().__init_subclass__(**kwargs)
        check_dishka()

    def __init__(self) -> None:
        """Check dishka availability when instantiating."""
        check_dishka()
        super().__init__()


__all__ = ["BaseDishkaProvider"]
