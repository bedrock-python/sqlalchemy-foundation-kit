"""Unit tests for dependency-injector database providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Helper Functions Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test___create_session_manager_resource__without_healthcheck__creates_manager() -> None:
    # Arrange
    mock_config = MagicMock()
    mock_metrics = MagicMock()
    mock_manager = AsyncMock()
    mock_manager.aclose = AsyncMock()

    with patch(
        "sqlalchemy_foundation_kit.contrib.dependency_injector.database.create_async_session_manager",
        return_value=mock_manager,
    ):
        from sqlalchemy_foundation_kit.contrib.dependency_injector.database import _create_session_manager_resource

        # Act - Use async for to consume the async generator
        gen = _create_session_manager_resource(mock_config, mock_metrics, None, MagicMock())
        manager = await gen.__anext__()

        # Assert
        assert manager == mock_manager

        # Cleanup
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test___create_session_manager_resource__cleanup_error__logs_warning() -> None:
    """Test that cleanup errors are logged but don't raise."""
    # Arrange
    from sqlalchemy.exc import SQLAlchemyError

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import _create_session_manager_resource

    mock_config = MagicMock()
    mock_manager = AsyncMock()
    mock_manager.aclose = AsyncMock(side_effect=SQLAlchemyError("cleanup error"))

    with patch(
        "sqlalchemy_foundation_kit.contrib.dependency_injector.database.create_async_session_manager",
        return_value=mock_manager,
    ):
        # Act
        gen = _create_session_manager_resource(mock_config, None, None, MagicMock())
        manager = await gen.__anext__()

        # Cleanup - should log warning but not raise
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

        # Assert
        assert manager == mock_manager
        mock_manager.aclose.assert_called_once()


@pytest.mark.unit
def test___get_session_maker__extracts_session_maker() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_manager = MagicMock()
    mock_manager.session_maker = mock_session_maker

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import _get_session_maker

    # Act
    result = _get_session_maker(mock_manager)

    # Assert
    assert result == mock_session_maker


@pytest.mark.unit
def test___create_uow__creates_unit_of_work() -> None:
    # Arrange
    mock_session_maker = MagicMock()

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import _create_uow

    # Act
    uow = _create_uow(mock_session_maker)

    # Assert
    assert uow is not None


# ============================================================================
# AsyncDatabaseResourceProvider Tests
# ============================================================================


@pytest.mark.unit
def test__async_database_resource_provider__init__succeeds() -> None:
    # Arrange
    mock_config = MagicMock()
    mock_metrics = MagicMock()

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

    # Act
    provider = AsyncDatabaseResourceProvider(
        postgres_config=mock_config,
        metrics=mock_metrics,
        healthcheck_query="SELECT 1",
    )

    # Assert
    assert provider._postgres_config == mock_config
    assert provider._metrics == mock_metrics
    assert provider._healthcheck_query == "SELECT 1"


@pytest.mark.unit
def test__async_database_resource_provider__init_default_params__succeeds() -> None:
    # Arrange
    mock_config = MagicMock()

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

    # Act
    provider = AsyncDatabaseResourceProvider(postgres_config=mock_config)

    # Assert
    assert provider._postgres_config == mock_config
    assert provider._metrics is None


@pytest.mark.unit
def test__async_database_resource_provider__init_skip_healthcheck__succeeds() -> None:
    # Arrange
    mock_config = MagicMock()

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

    # Act
    provider = AsyncDatabaseResourceProvider(
        postgres_config=mock_config,
        healthcheck_query=None,
    )

    # Assert
    assert provider._healthcheck_query is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test__async_database_resource_provider__start_without_healthcheck__creates_manager() -> None:
    # Arrange
    mock_config = MagicMock()
    mock_manager = AsyncMock()

    with patch(
        "sqlalchemy_foundation_kit.contrib.dependency_injector.database.create_async_session_manager",
        return_value=mock_manager,
    ):
        from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

        provider = AsyncDatabaseResourceProvider(
            postgres_config=mock_config,
            healthcheck_query=None,
        )

        # Act
        manager = await provider.start()

        # Assert
        assert manager == mock_manager
        assert provider._manager == mock_manager


@pytest.mark.unit
@pytest.mark.asyncio
async def test__async_database_resource_provider__stop__closes_manager() -> None:
    # Arrange
    mock_config = MagicMock()
    mock_manager = AsyncMock()
    mock_manager.aclose = AsyncMock()

    with patch(
        "sqlalchemy_foundation_kit.contrib.dependency_injector.database.create_async_session_manager",
        return_value=mock_manager,
    ):
        from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

        provider = AsyncDatabaseResourceProvider(
            postgres_config=mock_config,
            healthcheck_query=None,
        )

        await provider.start()

        # Act
        await provider.stop()

        # Assert
        mock_manager.aclose.assert_called_once()
        assert provider._manager is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test__async_database_resource_provider__stop_when_not_started__does_nothing() -> None:
    # Arrange
    mock_config = MagicMock()

    from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

    provider = AsyncDatabaseResourceProvider(postgres_config=mock_config)

    # Act & Assert - should not raise
    await provider.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test__async_database_resource_provider__stop_on_error__handles_gracefully() -> None:
    # Arrange
    from sqlalchemy.exc import SQLAlchemyError

    mock_config = MagicMock()
    mock_manager = AsyncMock()
    mock_manager.aclose = AsyncMock(side_effect=SQLAlchemyError("close error"))

    with patch(
        "sqlalchemy_foundation_kit.contrib.dependency_injector.database.create_async_session_manager",
        return_value=mock_manager,
    ):
        from sqlalchemy_foundation_kit.contrib.dependency_injector.database import AsyncDatabaseResourceProvider

        provider = AsyncDatabaseResourceProvider(
            postgres_config=mock_config,
            healthcheck_query=None,
        )

        await provider.start()

        # Act - should log warning but not raise
        await provider.stop()

        # Assert
        assert provider._manager is None
