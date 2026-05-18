"""Unit tests for telemetry instrumentation functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# instrument_sqlalchemy Tests
# ============================================================================


@pytest.mark.unit
def test__instrument_sqlalchemy__no_otel__raises_import_error() -> None:
    # Arrange
    with patch.dict("sys.modules", {"opentelemetry.instrumentation.sqlalchemy": None}):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_sqlalchemy

        # Act & Assert
        with pytest.raises(ImportError, match="opentelemetry-instrumentation-sqlalchemy"):
            instrument_sqlalchemy()


@pytest.mark.unit
def test__instrument_sqlalchemy__with_otel_installed__calls_instrumentor() -> None:
    # Arrange
    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.sqlalchemy": MagicMock(SQLAlchemyInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_sqlalchemy

        # Act
        instrument_sqlalchemy()

        # Assert
        mock_instrumentor_instance.instrument.assert_called_once_with()


@pytest.mark.unit
def test__instrument_sqlalchemy__with_engine__passes_engine_to_instrumentor() -> None:
    # Arrange
    mock_engine = MagicMock()
    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.sqlalchemy": MagicMock(SQLAlchemyInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_sqlalchemy

        # Act
        instrument_sqlalchemy(engine=mock_engine)

        # Assert
        mock_instrumentor_instance.instrument.assert_called_once_with(engine=mock_engine)


@pytest.mark.unit
def test__instrument_sqlalchemy__with_kwargs__passes_kwargs_to_instrumentor() -> None:
    # Arrange
    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.sqlalchemy": MagicMock(SQLAlchemyInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_sqlalchemy

        # Act
        instrument_sqlalchemy(enable_commenter=True, tracer_provider=MagicMock())

        # Assert
        call_args = mock_instrumentor_instance.instrument.call_args
        assert "enable_commenter" in call_args.kwargs
        assert "tracer_provider" in call_args.kwargs


# ============================================================================
# instrument_engine Tests
# ============================================================================


@pytest.mark.unit
def test__instrument_engine__no_otel__raises_import_error() -> None:
    # Arrange
    mock_async_engine = MagicMock()
    mock_async_engine.sync_engine = MagicMock()

    with patch.dict("sys.modules", {"opentelemetry.instrumentation.sqlalchemy": None}):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_engine

        # Act & Assert
        with pytest.raises(ImportError, match="opentelemetry-instrumentation-sqlalchemy"):
            instrument_engine(mock_async_engine)


@pytest.mark.unit
def test__instrument_engine__with_otel__instruments_sync_engine() -> None:
    # Arrange
    mock_sync_engine = MagicMock()
    mock_async_engine = MagicMock()
    mock_async_engine.sync_engine = mock_sync_engine

    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.sqlalchemy": MagicMock(SQLAlchemyInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_engine

        # Act
        instrument_engine(mock_async_engine)

        # Assert
        mock_instrumentor_instance.instrument.assert_called_once_with(engine=mock_sync_engine)


@pytest.mark.unit
def test__instrument_engine__with_kwargs__passes_kwargs() -> None:
    # Arrange
    mock_sync_engine = MagicMock()
    mock_async_engine = MagicMock()
    mock_async_engine.sync_engine = mock_sync_engine

    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.sqlalchemy": MagicMock(SQLAlchemyInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_engine

        # Act
        instrument_engine(mock_async_engine, enable_commenter=True)

        # Assert
        call_args = mock_instrumentor_instance.instrument.call_args
        assert "engine" in call_args.kwargs
        assert call_args.kwargs["engine"] == mock_sync_engine
        assert "enable_commenter" in call_args.kwargs


# ============================================================================
# instrument_asyncpg Tests
# ============================================================================


@pytest.mark.unit
def test__instrument_asyncpg__no_otel__raises_import_error() -> None:
    # Arrange
    with patch.dict("sys.modules", {"opentelemetry.instrumentation.asyncpg": None}):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_asyncpg

        # Act & Assert
        with pytest.raises(ImportError, match="opentelemetry-instrumentation-asyncpg"):
            instrument_asyncpg()


@pytest.mark.unit
def test__instrument_asyncpg__with_otel_installed__calls_instrumentor() -> None:
    # Arrange
    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.asyncpg": MagicMock(AsyncPGInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_asyncpg

        # Act
        instrument_asyncpg()

        # Assert
        mock_instrumentor_instance.instrument.assert_called_once_with()


@pytest.mark.unit
def test__instrument_asyncpg__with_kwargs__passes_kwargs_to_instrumentor() -> None:
    # Arrange
    mock_instrumentor_class = MagicMock()
    mock_instrumentor_instance = MagicMock()
    mock_instrumentor_class.return_value = mock_instrumentor_instance

    with patch.dict(
        "sys.modules",
        {"opentelemetry.instrumentation.asyncpg": MagicMock(AsyncPGInstrumentor=mock_instrumentor_class)},
    ):
        from sqlalchemy_foundation_kit.contrib.telemetry.instrumentations import instrument_asyncpg

        # Act
        instrument_asyncpg(tracer_provider=MagicMock())

        # Assert
        call_args = mock_instrumentor_instance.instrument.call_args
        assert "tracer_provider" in call_args.kwargs
