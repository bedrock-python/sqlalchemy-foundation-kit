"""OpenTelemetry instrumentation functions for SQLAlchemy and asyncpg."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


def instrument_sqlalchemy(engine: Any | None = None, **kwargs: Any) -> None:
    """Instrument SQLAlchemy engine for OpenTelemetry tracing.

    Automatically traces all SQLAlchemy operations including queries,
    commits, and rollbacks.

    Args:
        engine: Optional SQLAlchemy engine to instrument. If None, all engines.
        **kwargs: Additional keyword arguments passed to SQLAlchemyInstrumentor.

    Raises:
        ImportError: If opentelemetry-instrumentation-sqlalchemy is not installed.

    Examples:
        >>> from sqlalchemy import create_engine
        >>> from sqlalchemy_foundation_kit.contrib.telemetry import instrument_sqlalchemy
        >>> engine = create_engine("postgresql://...")
        >>> instrument_sqlalchemy(engine=engine)
    """
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # noqa: PLC0415
    except ImportError as e:
        raise ImportError(
            "opentelemetry-instrumentation-sqlalchemy not installed. "
            "Install with: pip install 'sqlalchemy-foundation-kit[telemetry]'"
        ) from e

    call_kwargs: dict[str, Any] = dict(kwargs)
    if engine is not None:
        call_kwargs["engine"] = engine

    SQLAlchemyInstrumentor().instrument(**call_kwargs)


def instrument_engine(engine: AsyncEngine, **kwargs: Any) -> None:
    """Attach OpenTelemetry tracing to a specific async SQLAlchemy engine.

    Designed to be passed as the ``on_engine_created`` hook of
    :class:`~sqlalchemy_foundation_kit.session.AsyncSessionManager` or
    :func:`~sqlalchemy_foundation_kit.session.create_async_session_manager`.

    Args:
        engine: The AsyncEngine to instrument.
        **kwargs: Additional keyword arguments passed to SQLAlchemyInstrumentor.

    Raises:
        ImportError: If opentelemetry-instrumentation-sqlalchemy is not installed.

    Examples:
        >>> from sqlalchemy_foundation_kit.session import create_async_session_manager
        >>> from sqlalchemy_foundation_kit.contrib.telemetry import instrument_engine
        >>> manager = create_async_session_manager(config, on_engine_created=instrument_engine)
    """
    instrument_sqlalchemy(engine=engine.sync_engine, **kwargs)


def instrument_asyncpg(**kwargs: Any) -> None:
    """Instrument asyncpg connections for OpenTelemetry tracing.

    Automatically traces all asyncpg database operations at the connection level.

    Args:
        **kwargs: Additional keyword arguments passed to AsyncPGInstrumentor.

    Raises:
        ImportError: If opentelemetry-instrumentation-asyncpg is not installed.

    Examples:
        >>> from sqlalchemy_foundation_kit.contrib.telemetry import instrument_asyncpg
        >>> instrument_asyncpg()
    """
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor  # noqa: PLC0415
    except ImportError as e:
        raise ImportError(
            "opentelemetry-instrumentation-asyncpg not installed. "
            "Install with: pip install 'sqlalchemy-foundation-kit[telemetry]'"
        ) from e

    AsyncPGInstrumentor().instrument(**kwargs)


__all__ = [
    "instrument_asyncpg",
    "instrument_engine",
    "instrument_sqlalchemy",
]
