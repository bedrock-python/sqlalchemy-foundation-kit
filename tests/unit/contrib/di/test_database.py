"""Unit tests for dishka database providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# AsyncDatabaseProvider Tests
# ============================================================================


@pytest.mark.unit
def test__async_database_provider__init_default__succeeds() -> None:
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

            # Act
            provider = AsyncDatabaseProvider()

            # Assert
            assert provider._healthcheck_query == "SELECT 1"


@pytest.mark.unit
def test__async_database_provider__init_skip_healthcheck__succeeds() -> None:
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

            # Act
            provider = AsyncDatabaseProvider(healthcheck_query=None)

            # Assert
            assert provider._healthcheck_query is None


@pytest.mark.unit
def test__async_database_provider__init_custom_retry_config__succeeds() -> None:
    # Arrange
    mock_base_init = MagicMock()
    mock_retry_config = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

            # Act
            provider = AsyncDatabaseProvider(retry_config=mock_retry_config)

            # Assert
            assert provider._retry_config == mock_retry_config


@pytest.mark.unit
def test__async_database_provider__create_session_manager__calls_factory() -> None:
    # Arrange
    mock_config = MagicMock()
    mock_metrics = MagicMock()
    mock_manager = MagicMock()
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            with patch(
                "sqlalchemy_foundation_kit.contrib.di.database.create_async_session_manager",
                return_value=mock_manager,
            ) as mock_create:
                from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

                provider = AsyncDatabaseProvider()

                # Act
                result = provider.create_session_manager(mock_config, mock_metrics)

                # Assert
                assert result == mock_manager
                mock_create.assert_called_once_with(mock_config, metrics=mock_metrics)


@pytest.mark.unit
def test__async_database_provider__get_session_maker__extracts_from_manager() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_manager = MagicMock()
    mock_manager.session_maker = mock_session_maker
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

            provider = AsyncDatabaseProvider()

            # Act
            result = provider.get_session_maker(mock_manager)

            # Assert
            assert result == mock_session_maker


@pytest.mark.unit
@pytest.mark.asyncio
async def test__async_database_provider__get_session_manager_cleanup_error__logs_warning() -> None:
    """Test that cleanup errors in get_session_manager are logged but don't raise."""
    # Arrange
    from sqlalchemy.exc import SQLAlchemyError

    from sqlalchemy_foundation_kit.contrib.di.database import AsyncDatabaseProvider

    mock_config = MagicMock()
    mock_manager = AsyncMock()
    mock_manager.aclose = AsyncMock(side_effect=SQLAlchemyError("cleanup error"))
    mock_manager.session_maker = MagicMock()

    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            with patch(
                "sqlalchemy_foundation_kit.contrib.di.database.create_async_session_manager",
                return_value=mock_manager,
            ):
                provider = AsyncDatabaseProvider(healthcheck_query=None)

                # Act
                gen = provider.get_session_manager(mock_config, None)
                manager = await gen.__anext__()

                # Cleanup - should log warning but not raise
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

                # Assert
                assert manager == mock_manager
                mock_manager.aclose.assert_called_once()


# ============================================================================
# AsyncUnitOfWorkProvider Tests
# ============================================================================


@pytest.mark.unit
def test__async_unit_of_work_provider__init__succeeds() -> None:
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncUnitOfWorkProvider

            # Act
            provider = AsyncUnitOfWorkProvider()

            # Assert
            assert provider is not None


@pytest.mark.unit
def test__async_unit_of_work_provider__create_uow__returns_uow() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncUnitOfWorkProvider

            provider = AsyncUnitOfWorkProvider()

            # Act
            uow = provider.create_uow(mock_session_maker)

            # Assert
            assert uow is not None


@pytest.mark.unit
def test__async_unit_of_work_provider__get_uow__returns_uow() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.database import AsyncUnitOfWorkProvider

            provider = AsyncUnitOfWorkProvider()

            # Act
            uow = provider.get_uow(mock_session_maker)

            # Assert
            assert uow is not None
