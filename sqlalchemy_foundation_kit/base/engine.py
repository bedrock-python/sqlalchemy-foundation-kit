"""SQLAlchemy engine configuration utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from sqlalchemy.pool import (
    AsyncAdaptedQueuePool,
    FallbackAsyncAdaptedQueuePool,
    NullPool,
    QueuePool,
    SingletonThreadPool,
    StaticPool,
)

if TYPE_CHECKING:
    from ..config import PoolSettingsProtocol

PoolClassStr = Literal[
    "null", "queue", "singleton_thread", "async_adapted_queue", "fallback_async_adapted_queue", "static"
]

_POOL_CLASSES: dict[str, type] = {
    "null": NullPool,
    "queue": QueuePool,
    "singleton_thread": SingletonThreadPool,
    "async_adapted_queue": AsyncAdaptedQueuePool,
    "fallback_async_adapted_queue": FallbackAsyncAdaptedQueuePool,
    "static": StaticPool,
}


def resolve_pool_class(poolclass: PoolClassStr | str | type) -> type:
    """Resolve pool class from string name or return the class directly.

    Args:
        poolclass: Pool class name (e.g., "null", "queue") or actual class type.

    Returns:
        Pool class type.

    Raises:
        ValueError: If pool class name is not recognized.

    Examples:
        >>> resolve_pool_class("null")
        <class 'sqlalchemy.pool.NullPool'>
        >>> resolve_pool_class(NullPool)
        <class 'sqlalchemy.pool.NullPool'>
    """
    if isinstance(poolclass, str):
        try:
            return _POOL_CLASSES[poolclass.lower()]
        except KeyError as e:
            available = ", ".join(sorted(_POOL_CLASSES.keys()))
            raise ValueError(f"Unknown pool class: {poolclass}. Available: {available}") from e

    return poolclass


def build_engine_kwargs(
    echo: bool,
    poolclass: type,
    isolation_level: str | None,
    pool_settings: PoolSettingsProtocol | None,
    connect_args: dict[str, object] | None,
    extra_kwargs: dict[str, object],
    use_orjson: bool = False,
) -> dict[str, object]:
    """Build SQLAlchemy engine keyword arguments.

    Args:
        echo: If True, SQLAlchemy will log all SQL statements.
        poolclass: SQLAlchemy pool class.
        isolation_level: Default transaction isolation level.
        pool_settings: Pool configuration settings (validated by caller, e.g., Pydantic).
        connect_args: Arguments passed to the database driver.
        extra_kwargs: Additional keyword arguments for create_async_engine.
        use_orjson: If True, use orjson for JSON serialization.

    Returns:
        Dictionary of engine keyword arguments ready for create_async_engine().

    Raises:
        ImportError: If use_orjson is True but orjson is not installed.

    Examples:
        >>> kwargs = build_engine_kwargs(
        ...     echo=False,
        ...     poolclass=NullPool,
        ...     isolation_level=None,
        ...     pool_settings=None,
        ...     connect_args=None,
        ...     extra_kwargs={},
        ...     use_orjson=False,
        ... )
        >>> kwargs["echo"]
        False
    """
    engine_kwargs: dict[str, object] = {
        "echo": echo,
        "poolclass": poolclass,
        "isolation_level": isolation_level,
        "pool_pre_ping": pool_settings.pre_ping if pool_settings else True,
    }

    if use_orjson:
        from .serialization import configure_orjson_serialization  # noqa: PLC0415

        engine_kwargs.update(configure_orjson_serialization())

    if pool_settings:
        _apply_pool_settings(engine_kwargs, poolclass, pool_settings)

    if connect_args:
        engine_kwargs["connect_args"] = {k: v for k, v in connect_args.items() if v is not None}

    if extra_kwargs:
        engine_kwargs.update(extra_kwargs)

    return engine_kwargs


def _apply_pool_settings(
    engine_kwargs: dict[str, object],
    poolclass: type,
    pool_settings: PoolSettingsProtocol,
) -> None:
    """Apply pool settings to engine kwargs.

    Maps pool settings to SQLAlchemy's expected ``pool_*`` keyword arguments.
    Note: pool_pre_ping is already set in build_engine_kwargs, so not applied here.

    Only applies pool size/overflow/recycle/timeout for pool classes that support them.
    Checks if the pool class accepts these parameters via hasattr to avoid passing
    unsupported kwargs to pools like NullPool or StaticPool.

    Args:
        engine_kwargs: Dictionary to update with pool configuration.
        poolclass: Pool class being configured.
        pool_settings: Pool configuration settings.
    """
    # Build pool parameters dict
    params = {
        "pool_size": pool_settings.size,
        "max_overflow": pool_settings.max_overflow,
        "pool_recycle": pool_settings.recycle,
        "pool_timeout": pool_settings.timeout,
    }

    # Apply only non-None parameters
    # SQLAlchemy pool classes that don't support these params will ignore them
    # or raise TypeError if passed, so we rely on the pool class itself to validate
    engine_kwargs.update({k: v for k, v in params.items() if v is not None})


__all__ = [
    "PoolClassStr",
    "build_engine_kwargs",
    "resolve_pool_class",
]
