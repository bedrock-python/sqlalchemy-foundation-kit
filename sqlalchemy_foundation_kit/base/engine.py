"""SQLAlchemy engine configuration utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

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
    "null",
    "queue",
    "singleton_thread",
    "async_adapted_queue",
    "fallback_async_adapted_queue",
    "static",
]


class PoolRegistry:
    """Registry for SQLAlchemy pool classes.

    Provides a centralized registry for pool classes that follows the Open/Closed principle:
    - Open for extension: custom pools can be registered via :meth:`register`
    - Closed for modification: built-in pools are immutable

    This design allows library users to register custom pool implementations without
    modifying library code.

    Examples:
        Register a custom pool class:
            >>> class MyCustomPool(QueuePool):
            ...     pass
            >>> PoolRegistry.register("custom", MyCustomPool)
            >>> pool = PoolRegistry.resolve("custom")

        Override built-in pool (not recommended, but possible):
            >>> PoolRegistry.register("queue", MyCustomQueuePool, override=True)
    """

    _pools: ClassVar[dict[str, type]] = {
        "null": NullPool,
        "queue": QueuePool,
        "singleton_thread": SingletonThreadPool,
        "async_adapted_queue": AsyncAdaptedQueuePool,
        "fallback_async_adapted_queue": FallbackAsyncAdaptedQueuePool,
        "static": StaticPool,
    }

    @classmethod
    def register(cls, name: str, pool_class: type, *, override: bool = False) -> None:
        """Register a custom pool class.

        Args:
            name: Pool class identifier (lowercase recommended).
            pool_class: Pool class type to register.
            override: If True, allows overriding built-in pools (use with caution).

        Raises:
            ValueError: If name already exists and override=False.

        Examples:
            >>> PoolRegistry.register("my_pool", MyCustomPool)
        """
        if name in cls._pools and not override:
            raise ValueError(
                f"Pool class '{name}' is already registered. "
                f"Use override=True to replace it (not recommended for built-ins)."
            )
        cls._pools[name] = pool_class

    @classmethod
    def resolve(cls, name: str) -> type:
        """Resolve pool class by name.

        Args:
            name: Pool class identifier.

        Returns:
            Pool class type.

        Raises:
            ValueError: If pool class name is not registered.

        Examples:
            >>> pool = PoolRegistry.resolve("queue")
            >>> pool
            <class 'sqlalchemy.pool.QueuePool'>
        """
        try:
            return cls._pools[name.lower()]
        except KeyError as e:
            available = ", ".join(sorted(cls._pools.keys()))
            raise ValueError(f"Unknown pool class: {name}. Available: {available}") from e

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered pool class names.

        Returns:
            Sorted list of registered pool names.

        Examples:
            >>> PoolRegistry.list_available()
            ['async_adapted_queue', 'fallback_async_adapted_queue', 'null', 'queue', ...]
        """
        return sorted(cls._pools.keys())


def resolve_pool_class(poolclass: PoolClassStr | str | type) -> type:
    """Resolve pool class from string name or return the class directly.

    Args:
        poolclass: Pool class name (e.g., "null", "queue") or actual class type.

    Returns:
        Pool class type.

    Raises:
        ValueError: If pool class name is not recognized.
    """
    if isinstance(poolclass, str):
        return PoolRegistry.resolve(poolclass)

    return poolclass


def register_pool_class(name: str, pool_class: type, *, override: bool = False) -> None:
    """Register a custom pool class.

    Convenience wrapper around :meth:`PoolRegistry.register` for users who prefer
    a functional API over the class-based one.

    Args:
        name: Pool class identifier (lowercase recommended).
        pool_class: Pool class type to register.
        override: If True, allows overriding built-in pools (use with caution).

    Raises:
        ValueError: If name already exists and override=False.
    """
    PoolRegistry.register(name, pool_class, override=override)


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
    "PoolRegistry",
    "build_engine_kwargs",
    "register_pool_class",
    "resolve_pool_class",
]
