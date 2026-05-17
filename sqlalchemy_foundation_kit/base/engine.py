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
    from ..config import PoolConfig

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

_UNPOOLED_CLASSES: set[type] = {NullPool, StaticPool, SingletonThreadPool}


def register_pool_class(name: str, pool_class: type, *, unpooled: bool = False) -> None:
    """Register a custom pool class under a string name.

    Enables extension with custom pool implementations without modifying the library.

    Args:
        name: String identifier (case-insensitive).
        pool_class: Pool class to register.
        unpooled: If True, treat as unpooled (no pool_size/overflow applied).

    Examples:
        >>> from sqlalchemy.pool import QueuePool
        >>> register_pool_class("my_queue", QueuePool)
        >>> resolve_pool_class("my_queue")
        <class 'sqlalchemy.pool.QueuePool'>
    """
    _POOL_CLASSES[name.lower()] = pool_class
    if unpooled:
        _UNPOOLED_CLASSES.add(pool_class)


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
    pool_config: PoolConfig | None,
    connect_args: dict[str, object] | None,
    extra_kwargs: dict[str, object],
    use_orjson: bool = False,
) -> dict[str, object]:
    """Build SQLAlchemy engine keyword arguments with validation.

    Args:
        echo: If True, SQLAlchemy will log all SQL statements.
        poolclass: SQLAlchemy pool class.
        isolation_level: Default transaction isolation level.
        pool_config: Pool configuration settings.
        connect_args: Arguments passed to the database driver.
        extra_kwargs: Additional keyword arguments for create_async_engine.
        use_orjson: If True, use orjson for JSON serialization.

    Returns:
        Dictionary of engine keyword arguments ready for create_async_engine().

    Raises:
        ValueError: If pool_config contains invalid values.
        ImportError: If use_orjson is True but orjson is not installed.

    Examples:
        >>> kwargs = build_engine_kwargs(
        ...     echo=False,
        ...     poolclass=NullPool,
        ...     isolation_level=None,
        ...     pool_config=None,
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
        "pool_pre_ping": True,
    }

    if use_orjson:
        from .serialization import configure_orjson_serialization  # noqa: PLC0415

        engine_kwargs.update(configure_orjson_serialization())

    if pool_config:
        _validate_pool_config(pool_config)
        _apply_pool_config(engine_kwargs, poolclass, pool_config)

    if connect_args:
        engine_kwargs["connect_args"] = {k: v for k, v in connect_args.items() if v is not None}

    if extra_kwargs:
        engine_kwargs.update(extra_kwargs)

    return engine_kwargs


def _validate_pool_config(pool_config: PoolConfig) -> None:
    """Validate pool configuration values.

    Args:
        pool_config: Pool configuration to validate.

    Raises:
        ValueError: If any configuration value is invalid.
    """
    if pool_config.size is not None and pool_config.size < 0:
        raise ValueError(f"size must be non-negative, got {pool_config.size}")

    if pool_config.max_overflow is not None and pool_config.max_overflow < -1:
        raise ValueError(f"max_overflow must be >= -1, got {pool_config.max_overflow}")

    if pool_config.timeout is not None and pool_config.timeout < 0:
        raise ValueError(f"timeout must be non-negative, got {pool_config.timeout}")

    if pool_config.recycle is not None and pool_config.recycle < -1:
        raise ValueError(f"recycle must be >= -1, got {pool_config.recycle}")


def _apply_pool_config(
    engine_kwargs: dict[str, object],
    poolclass: type,
    pool_config: PoolConfig,
) -> None:
    """Apply pool configuration to engine kwargs.

    Maps internal field names to SQLAlchemy's expected ``pool_*`` keyword arguments.

    Args:
        engine_kwargs: Dictionary to update with pool configuration.
        poolclass: Pool class being configured.
        pool_config: Pool configuration settings.
    """
    if pool_config.pre_ping is not None:
        engine_kwargs["pool_pre_ping"] = pool_config.pre_ping

    # Only apply pool size/overflow settings for pooled connections
    if poolclass not in _UNPOOLED_CLASSES:
        params = {
            "pool_size": pool_config.size,
            "max_overflow": pool_config.max_overflow,
            "pool_recycle": pool_config.recycle,
            "pool_timeout": pool_config.timeout,
        }
        engine_kwargs.update({k: v for k, v in params.items() if v is not None})


__all__ = [
    "PoolClassStr",
    "build_engine_kwargs",
    "register_pool_class",
    "resolve_pool_class",
]
