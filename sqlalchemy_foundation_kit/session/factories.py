"""Async database session manager factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import PostgresSettingsProtocol
from .connection import AsyncCConnection
from .manager import AsyncSessionManager

if TYPE_CHECKING:
    from collections.abc import Callable

    import asyncpg
    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..protocols import PostgresMetricsProtocol


def create_async_session_manager(
    postgres_config: PostgresSettingsProtocol,
    application_name: str | None = None,
    metrics: PostgresMetricsProtocol | None = None,
    on_engine_created: Callable[[AsyncEngine], None] | None = None,
    connection_class: type[asyncpg.Connection] | None = None,
    extra_server_settings: dict[str, str] | None = None,
    extra_connect_args: dict[str, object] | None = None,
    **kwargs: Any,
) -> AsyncSessionManager[AsyncSession]:
    """Create async session manager with PostgreSQL-specific configuration.

    Args:
        postgres_config: PostgreSQL configuration implementing PostgresSettingsProtocol.
        application_name: Optional custom application name. If None, uses postgres_config.application_name.
        metrics: Optional metrics collector for connection pool monitoring.
        on_engine_created: Optional callback invoked with the AsyncEngine right after creation.
            Use it to attach OpenTelemetry instrumentation, custom listeners, etc.
        connection_class: Custom asyncpg Connection subclass. Defaults to ``AsyncCConnection``
            which provides pgbouncer transaction-mode compatibility.
        extra_server_settings: Additional PostgreSQL ``server_settings`` to merge with defaults
            (e.g., ``{"statement_timeout": "30000", "timezone": "UTC"}``). User-provided keys
            override library defaults.
        extra_connect_args: Additional asyncpg ``connect_args`` to merge with defaults
            (e.g., ``{"command_timeout": 60}``). User-provided keys override library defaults.
        **kwargs: Additional keyword arguments passed to AsyncSessionManager.

    Returns:
        Configured AsyncSessionManager instance.

    Examples:
        Basic usage:
            >>> manager = create_async_session_manager(postgres_config)

        With metrics:
            >>> from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics
            >>> manager = create_async_session_manager(postgres_config, metrics=PostgresMetrics())

        With custom server settings and command timeout:
            >>> manager = create_async_session_manager(
            ...     postgres_config,
            ...     extra_server_settings={"statement_timeout": "30000", "timezone": "UTC"},
            ...     extra_connect_args={"command_timeout": 60},
            ... )

        With OpenTelemetry tracing bound to this engine:
            >>> from sqlalchemy_foundation_kit.contrib.telemetry import instrument_engine
            >>> manager = create_async_session_manager(
            ...     postgres_config,
            ...     on_engine_created=instrument_engine,
            ... )
    """
    app_name = application_name or postgres_config.application_name

    # Build server settings with optional overrides
    server_settings: dict[str, str] = {
        "application_name": app_name,
        **({"jit": postgres_config.jit} if postgres_config.jit is not None else {}),
        **({"search_path": postgres_config.db_schema} if postgres_config.db_schema is not None else {}),
        **(extra_server_settings or {}),
    }

    # Build connect args with optional overrides
    connect_args: dict[str, object] = {
        "server_settings": server_settings,
        "statement_cache_size": postgres_config.query.statement_cache_size,
        "prepared_statement_cache_size": postgres_config.query.prepared_statement_cache_size,
        "connection_class": connection_class or AsyncCConnection,
        **(extra_connect_args or {}),
    }

    return AsyncSessionManager(
        url=postgres_config.to_dsn(),
        echo=postgres_config.query.echo,
        poolclass=postgres_config.pool.kind,
        connect_args=connect_args,
        isolation_level=postgres_config.query.isolation_level,
        pool_settings=postgres_config.pool,
        use_orjson=postgres_config.use_orjson_serialization,
        metrics=metrics,
        on_engine_created=on_engine_created,
        **kwargs,
    )
