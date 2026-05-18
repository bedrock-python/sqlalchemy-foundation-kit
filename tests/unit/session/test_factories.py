"""Unit tests for async session manager factory."""

from __future__ import annotations

from unittest.mock import Mock, patch

import asyncpg
import pytest

from sqlalchemy_foundation_kit.session.connection import AsyncCConnection
from sqlalchemy_foundation_kit.session.factories import create_async_session_manager

# ============================================================================
# create_async_session_manager - Basic Tests
# ============================================================================


def test__create_async_session_manager__minimal_config__creates_manager() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        result = create_async_session_manager(mock_config)

    # Assert
    mock_manager_class.assert_called_once()
    assert result == mock_manager_class.return_value


def test__create_async_session_manager__minimal_config__passes_url() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://user:pass@localhost:5432/dbname"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["url"] == "postgresql://user:pass@localhost:5432/dbname"


def test__create_async_session_manager__minimal_config__uses_config_application_name() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "my-service"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "queue"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    assert server_settings["application_name"] == "my-service"


# ============================================================================
# create_async_session_manager - Application Name Tests
# ============================================================================


def test__create_async_session_manager__custom_application_name__overrides_config() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "config-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, application_name="custom-app")

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    assert server_settings["application_name"] == "custom-app"


# ============================================================================
# create_async_session_manager - Server Settings Tests
# ============================================================================


@pytest.mark.parametrize(
    "jit_value,should_be_in_settings",
    [
        ("on", True),
        ("off", True),
        (None, False),
    ],
)
def test__create_async_session_manager__jit__handled_correctly(
    jit_value: str | None, should_be_in_settings: bool
) -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = jit_value
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    if should_be_in_settings:
        assert server_settings["jit"] == jit_value
    else:
        assert "jit" not in server_settings


@pytest.mark.parametrize(
    "db_schema,should_be_in_settings",
    [
        ("public", True),
        ("custom_schema", True),
        (None, False),
    ],
)
def test__create_async_session_manager__db_schema__handled_correctly(
    db_schema: str | None, should_be_in_settings: bool
) -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = db_schema
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    if should_be_in_settings:
        assert server_settings["search_path"] == db_schema
    else:
        assert "search_path" not in server_settings


def test__create_async_session_manager__extra_server_settings__merges_with_defaults() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    extra_settings = {"statement_timeout": "30000", "timezone": "UTC"}

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, extra_server_settings=extra_settings)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    assert server_settings["statement_timeout"] == "30000"
    assert server_settings["timezone"] == "UTC"
    assert server_settings["application_name"] == "test-app"


def test__create_async_session_manager__extra_server_settings__overrides_defaults() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = "off"
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    extra_settings = {"jit": "on"}

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, extra_server_settings=extra_settings)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    server_settings = call_kwargs["connect_args"]["server_settings"]
    assert server_settings["jit"] == "on"  # Extra settings override config


# ============================================================================
# create_async_session_manager - Connect Args Tests
# ============================================================================


def test__create_async_session_manager__default__includes_statement_cache_sizes() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 200
    mock_config.query.prepared_statement_cache_size = 150
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    connect_args = call_kwargs["connect_args"]
    assert connect_args["statement_cache_size"] == 200
    assert connect_args["prepared_statement_cache_size"] == 150


def test__create_async_session_manager__default__uses_async_c_connection() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    connect_args = call_kwargs["connect_args"]
    assert connect_args["connection_class"] == AsyncCConnection


def test__create_async_session_manager__custom_connection_class__overrides_default() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    class CustomConnection(asyncpg.Connection):
        pass

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, connection_class=CustomConnection)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    connect_args = call_kwargs["connect_args"]
    assert connect_args["connection_class"] == CustomConnection


def test__create_async_session_manager__extra_connect_args__merges_with_defaults() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    extra_args = {"command_timeout": 60, "timeout": 30}

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, extra_connect_args=extra_args)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    connect_args = call_kwargs["connect_args"]
    assert connect_args["command_timeout"] == 60
    assert connect_args["timeout"] == 30
    assert connect_args["statement_cache_size"] == 100


def test__create_async_session_manager__extra_connect_args__overrides_defaults() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    extra_args = {"statement_cache_size": 500}

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, extra_connect_args=extra_args)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    connect_args = call_kwargs["connect_args"]
    assert connect_args["statement_cache_size"] == 500  # Extra overrides


# ============================================================================
# create_async_session_manager - Manager Parameters Tests
# ============================================================================


@pytest.mark.parametrize(
    "param_name,config_setter,expected_value,factory_kwargs",
    [
        ("echo", lambda cfg: setattr(cfg.query, "echo", True), True, {}),
        ("poolclass", lambda cfg: setattr(cfg.pool, "kind", "async_adapted_queue"), "async_adapted_queue", {}),
        ("isolation_level", lambda cfg: setattr(cfg.query, "isolation_level", "SERIALIZABLE"), "SERIALIZABLE", {}),
        ("use_orjson", lambda cfg: setattr(cfg, "use_orjson_serialization", True), True, {}),
        ("metrics", lambda cfg: None, Mock(), {"metrics": Mock()}),
        ("on_engine_created", lambda cfg: None, Mock(), {"on_engine_created": Mock()}),
    ],
)
def test__create_async_session_manager__passes_parameters(
    param_name: str,
    config_setter: callable,
    expected_value: object,
    factory_kwargs: dict,
) -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Apply config changes
    config_setter(mock_config)

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config, **factory_kwargs)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    if factory_kwargs:
        # For kwargs passed to factory, use the actual value from factory_kwargs
        assert call_kwargs[param_name] is factory_kwargs[param_name]
    else:
        assert call_kwargs[param_name] == expected_value


def test__create_async_session_manager__passes_pool_settings() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "queue"
    mock_pool_settings = Mock()
    mock_config.pool = mock_pool_settings
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(mock_config)

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["pool_settings"] is mock_pool_settings


def test__create_async_session_manager__kwargs__passed_through() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "test-app"
    mock_config.jit = None
    mock_config.db_schema = None
    mock_config.query.statement_cache_size = 100
    mock_config.query.prepared_statement_cache_size = 100
    mock_config.query.echo = False
    mock_config.query.isolation_level = None
    mock_config.pool.kind = "null"
    mock_config.pool = Mock()
    mock_config.use_orjson_serialization = False
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(
            mock_config,
            custom_param1="value1",
            custom_param2=42,
        )

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["custom_param1"] == "value1"
    assert call_kwargs["custom_param2"] == 42


# ============================================================================
# create_async_session_manager - Integration Tests
# ============================================================================


def test__create_async_session_manager__all_options__combined() -> None:
    # Arrange
    mock_config = Mock()
    mock_config.application_name = "config-app"
    mock_config.jit = "off"
    mock_config.db_schema = "custom_schema"
    mock_config.query.statement_cache_size = 200
    mock_config.query.prepared_statement_cache_size = 150
    mock_config.query.echo = True
    mock_config.query.isolation_level = "READ COMMITTED"
    mock_pool = Mock()
    mock_pool.kind = "queue"
    mock_config.pool = mock_pool
    mock_config.use_orjson_serialization = True
    mock_config.to_dsn.return_value = "postgresql://localhost/test"

    mock_metrics = Mock()
    mock_callback = Mock()

    class CustomConn(asyncpg.Connection):
        pass

    extra_server = {"timezone": "UTC"}
    extra_connect = {"timeout": 30}

    # Act
    with patch("sqlalchemy_foundation_kit.session.factories.AsyncSessionManager") as mock_manager_class:
        create_async_session_manager(
            mock_config,
            application_name="override-app",
            metrics=mock_metrics,
            on_engine_created=mock_callback,
            connection_class=CustomConn,
            extra_server_settings=extra_server,
            extra_connect_args=extra_connect,
            extra_kwarg="test",
        )

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["url"] == "postgresql://localhost/test"
    assert call_kwargs["echo"] is True
    assert call_kwargs["poolclass"] == "queue"
    assert call_kwargs["isolation_level"] == "READ COMMITTED"
    assert call_kwargs["use_orjson"] is True
    assert call_kwargs["metrics"] is mock_metrics
    assert call_kwargs["on_engine_created"] is mock_callback
    assert call_kwargs["extra_kwarg"] == "test"

    connect_args = call_kwargs["connect_args"]
    assert connect_args["connection_class"] == CustomConn
    assert connect_args["statement_cache_size"] == 200
    assert connect_args["timeout"] == 30

    server_settings = connect_args["server_settings"]
    assert server_settings["application_name"] == "override-app"
    assert server_settings["jit"] == "off"
    assert server_settings["search_path"] == "custom_schema"
    assert server_settings["timezone"] == "UTC"
