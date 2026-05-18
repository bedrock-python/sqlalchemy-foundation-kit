"""Unit tests for AsyncSessionManagerBuilder."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from sqlalchemy_foundation_kit.session.builder import AsyncSessionManagerBuilder

# ============================================================================
# AsyncSessionManagerBuilder - Initialization Tests
# ============================================================================


def test__async_session_manager_builder__init__stores_url() -> None:
    # Arrange & Act
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Assert
    assert builder._url == "postgresql://localhost/test"


def test__async_session_manager_builder__init__sets_defaults() -> None:
    # Arrange & Act
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Assert
    assert builder._echo is False
    assert builder._poolclass == "null"
    assert builder._session_class is None
    assert builder._expire_on_commit is False
    assert builder._connect_args is None
    assert builder._isolation_level is None
    assert builder._pool_settings is None
    assert builder._use_orjson is False
    assert builder._metrics is None
    assert builder._on_engine_created is None
    assert builder._dispose_timeout is None
    assert builder._extra_kwargs == {}


# ============================================================================
# AsyncSessionManagerBuilder - with_echo Tests
# ============================================================================


def test__async_session_manager_builder__with_echo__returns_self() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    result = builder.with_echo(True)

    # Assert
    assert result is builder


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
    ],
)
def test__async_session_manager_builder__with_echo__sets_value(value: bool, expected: bool) -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_echo(value)

    # Assert
    assert builder._echo is expected


def test__async_session_manager_builder__with_echo__default_true() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_echo()

    # Assert
    assert builder._echo is True


# ============================================================================
# AsyncSessionManagerBuilder - Method Chaining (returns self)
# ============================================================================


@pytest.mark.parametrize(
    "method_name,args,kwargs",
    [
        ("with_echo", (True,), {}),
        ("with_pool", ("queue",), {}),
        ("with_session_class", (Mock,), {}),
        ("with_expire_on_commit", (True,), {}),
        ("with_connect_args", (), {"timeout": 30}),
        ("with_isolation_level", ("SERIALIZABLE",), {}),
        ("with_metrics", (Mock(),), {}),
        ("with_callbacks", (), {"on_engine_created": Mock()}),
        ("with_json_serialization", (True,), {}),
        ("with_extra_kwargs", (), {"custom": "value"}),
        ("with_dispose_timeout", (30.0,), {}),
    ],
)
def test__async_session_manager_builder__methods__return_self(method_name: str, args: tuple, kwargs: dict) -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")
    method = getattr(builder, method_name)

    # Act
    result = method(*args, **kwargs)

    # Assert
    assert result is builder


# ============================================================================
# AsyncSessionManagerBuilder - with_pool Tests
# ============================================================================


def test__async_session_manager_builder__with_pool__sets_poolclass() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_pool("async_adapted_queue")

    # Assert
    assert builder._poolclass == "async_adapted_queue"


def test__async_session_manager_builder__with_pool__sets_pool_settings() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")
    mock_pool_settings = Mock()

    # Act
    builder.with_pool("queue", pool_settings=mock_pool_settings)

    # Assert
    assert builder._poolclass == "queue"
    assert builder._pool_settings is mock_pool_settings


def test__async_session_manager_builder__with_pool__no_settings() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_pool("null")

    # Assert
    assert builder._pool_settings is None


# ============================================================================
# AsyncSessionManagerBuilder - with_session_class Tests
# ============================================================================


def test__async_session_manager_builder__with_session_class__sets_class() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")
    mock_session_class = Mock()

    # Act
    builder.with_session_class(mock_session_class)

    # Assert
    assert builder._session_class is mock_session_class


# ============================================================================
# AsyncSessionManagerBuilder - with_expire_on_commit Tests
# ============================================================================


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
    ],
)
def test__async_session_manager_builder__with_expire_on_commit__sets_value(value: bool, expected: bool) -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_expire_on_commit(value)

    # Assert
    assert builder._expire_on_commit is expected


def test__async_session_manager_builder__with_expire_on_commit__default_true() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_expire_on_commit()

    # Assert
    assert builder._expire_on_commit is True


# ============================================================================
# AsyncSessionManagerBuilder - with_connect_args Tests
# ============================================================================


def test__async_session_manager_builder__with_connect_args__initializes_dict() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_connect_args(timeout=30)

    # Assert
    assert builder._connect_args is not None
    assert builder._connect_args["timeout"] == 30


def test__async_session_manager_builder__with_connect_args__merges_args() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_connect_args(timeout=30)
    builder.with_connect_args(command_timeout=60)

    # Assert
    assert builder._connect_args["timeout"] == 30
    assert builder._connect_args["command_timeout"] == 60


def test__async_session_manager_builder__with_connect_args__updates_existing() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_connect_args(timeout=30)
    builder.with_connect_args(timeout=60)

    # Assert
    assert builder._connect_args["timeout"] == 60


def test__async_session_manager_builder__with_connect_args__multiple_keys() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_connect_args(
        timeout=30,
        command_timeout=60,
        server_settings={"app": "test"},
    )

    # Assert
    assert builder._connect_args["timeout"] == 30
    assert builder._connect_args["command_timeout"] == 60
    assert builder._connect_args["server_settings"] == {"app": "test"}


# ============================================================================
# AsyncSessionManagerBuilder - with_isolation_level Tests
# ============================================================================


def test__async_session_manager_builder__with_isolation_level__sets_level() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_isolation_level("READ COMMITTED")

    # Assert
    assert builder._isolation_level == "READ COMMITTED"


# ============================================================================
# AsyncSessionManagerBuilder - with_metrics Tests
# ============================================================================


def test__async_session_manager_builder__with_metrics__sets_metrics() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")
    mock_metrics = Mock()

    # Act
    builder.with_metrics(mock_metrics)

    # Assert
    assert builder._metrics is mock_metrics


# ============================================================================
# AsyncSessionManagerBuilder - with_callbacks Tests
# ============================================================================


def test__async_session_manager_builder__with_callbacks__sets_callback() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")
    mock_callback = Mock()

    # Act
    builder.with_callbacks(on_engine_created=mock_callback)

    # Assert
    assert builder._on_engine_created is mock_callback


# ============================================================================
# AsyncSessionManagerBuilder - with_json_serialization Tests
# ============================================================================


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
    ],
)
def test__async_session_manager_builder__with_json_serialization__sets_value(value: bool, expected: bool) -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_json_serialization(value)

    # Assert
    assert builder._use_orjson is expected


def test__async_session_manager_builder__with_json_serialization__default_true() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_json_serialization()

    # Assert
    assert builder._use_orjson is True


# ============================================================================
# AsyncSessionManagerBuilder - with_extra_kwargs Tests
# ============================================================================


def test__async_session_manager_builder__with_extra_kwargs__adds_kwargs() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_extra_kwargs(param1="value1", param2=42)

    # Assert
    assert builder._extra_kwargs["param1"] == "value1"
    assert builder._extra_kwargs["param2"] == 42


def test__async_session_manager_builder__with_extra_kwargs__merges_kwargs() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_extra_kwargs(param1="value1")
    builder.with_extra_kwargs(param2="value2")

    # Assert
    assert builder._extra_kwargs["param1"] == "value1"
    assert builder._extra_kwargs["param2"] == "value2"


def test__async_session_manager_builder__with_extra_kwargs__updates_existing() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_extra_kwargs(param="old")
    builder.with_extra_kwargs(param="new")

    # Assert
    assert builder._extra_kwargs["param"] == "new"


# ============================================================================
# AsyncSessionManagerBuilder - with_dispose_timeout Tests
# ============================================================================


def test__async_session_manager_builder__with_dispose_timeout__sets_timeout() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    builder.with_dispose_timeout(60.0)

    # Assert
    assert builder._dispose_timeout == 60.0


# ============================================================================
# AsyncSessionManagerBuilder - Method Chaining Tests
# ============================================================================


def test__async_session_manager_builder__method_chaining__works() -> None:
    # Arrange & Act
    builder = (
        AsyncSessionManagerBuilder("postgresql://localhost/test")
        .with_echo(True)
        .with_pool("queue")
        .with_isolation_level("SERIALIZABLE")
    )

    # Assert
    assert builder._echo is True
    assert builder._poolclass == "queue"
    assert builder._isolation_level == "SERIALIZABLE"


def test__async_session_manager_builder__method_chaining__all_methods() -> None:
    # Arrange
    mock_session_class = Mock()
    mock_pool_settings = Mock()
    mock_metrics = Mock()
    mock_callback = Mock()

    # Act
    builder = (
        AsyncSessionManagerBuilder("postgresql://localhost/test")
        .with_echo(True)
        .with_pool("queue", pool_settings=mock_pool_settings)
        .with_session_class(mock_session_class)
        .with_expire_on_commit(True)
        .with_connect_args(timeout=30)
        .with_isolation_level("READ COMMITTED")
        .with_metrics(mock_metrics)
        .with_callbacks(on_engine_created=mock_callback)
        .with_json_serialization(True)
        .with_extra_kwargs(custom="value")
        .with_dispose_timeout(45.0)
    )

    # Assert
    assert builder._url == "postgresql://localhost/test"
    assert builder._echo is True
    assert builder._poolclass == "queue"
    assert builder._pool_settings is mock_pool_settings
    assert builder._session_class is mock_session_class
    assert builder._expire_on_commit is True
    assert builder._connect_args["timeout"] == 30
    assert builder._isolation_level == "READ COMMITTED"
    assert builder._metrics is mock_metrics
    assert builder._on_engine_created is mock_callback
    assert builder._use_orjson is True
    assert builder._extra_kwargs["custom"] == "value"
    assert builder._dispose_timeout == 45.0


# ============================================================================
# AsyncSessionManagerBuilder - build Tests
# ============================================================================


def test__async_session_manager_builder__build__creates_manager() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        result = builder.build()

    # Assert
    mock_manager_class.assert_called_once()
    assert result == mock_manager_class.return_value


def test__async_session_manager_builder__build__passes_url() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://user:pass@host:5432/db")

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["url"] == "postgresql://user:pass@host:5432/db"


def test__async_session_manager_builder__build__passes_all_basic_params() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_echo(True).with_pool("queue")

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["url"] == "postgresql://localhost/test"
    assert call_kwargs["echo"] is True
    assert call_kwargs["poolclass"] == "queue"


def test__async_session_manager_builder__build__passes_optional_params() -> None:
    # Arrange
    mock_session_class = Mock()
    mock_pool_settings = Mock()
    mock_metrics = Mock()

    builder = (
        AsyncSessionManagerBuilder("postgresql://localhost/test")
        .with_session_class(mock_session_class)
        .with_pool("queue", pool_settings=mock_pool_settings)
        .with_expire_on_commit(True)
        .with_isolation_level("SERIALIZABLE")
        .with_metrics(mock_metrics)
        .with_json_serialization(True)
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["session_class"] is mock_session_class
    assert call_kwargs["poolclass"] == "queue"
    assert call_kwargs["pool_settings"] is mock_pool_settings
    assert call_kwargs["expire_on_commit"] is True
    assert call_kwargs["isolation_level"] == "SERIALIZABLE"
    assert call_kwargs["metrics"] is mock_metrics
    assert call_kwargs["use_orjson"] is True


def test__async_session_manager_builder__build__passes_connect_args() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_connect_args(
        timeout=30, command_timeout=60
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["connect_args"]["timeout"] == 30
    assert call_kwargs["connect_args"]["command_timeout"] == 60


def test__async_session_manager_builder__build__passes_callback() -> None:
    # Arrange
    mock_callback = Mock()
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_callbacks(on_engine_created=mock_callback)

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["on_engine_created"] is mock_callback


def test__async_session_manager_builder__build__includes_dispose_timeout() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_dispose_timeout(45.0)

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["dispose_timeout"] == 45.0


def test__async_session_manager_builder__build__excludes_none_dispose_timeout() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test")

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert "dispose_timeout" not in call_kwargs


def test__async_session_manager_builder__build__passes_extra_kwargs() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_extra_kwargs(
        custom_param1="value1", custom_param2=42
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["custom_param1"] == "value1"
    assert call_kwargs["custom_param2"] == 42


def test__async_session_manager_builder__build__all_params_combined() -> None:
    # Arrange
    mock_session_class = Mock()
    mock_pool_settings = Mock()
    mock_metrics = Mock()
    mock_callback = Mock()

    builder = (
        AsyncSessionManagerBuilder("postgresql://localhost/test")
        .with_echo(True)
        .with_pool("queue", pool_settings=mock_pool_settings)
        .with_session_class(mock_session_class)
        .with_expire_on_commit(True)
        .with_connect_args(timeout=30)
        .with_isolation_level("READ COMMITTED")
        .with_metrics(mock_metrics)
        .with_callbacks(on_engine_created=mock_callback)
        .with_json_serialization(True)
        .with_extra_kwargs(custom="value")
        .with_dispose_timeout(60.0)
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.build()

    # Assert
    call_kwargs = mock_manager_class.call_args[1]
    assert call_kwargs["url"] == "postgresql://localhost/test"
    assert call_kwargs["echo"] is True
    assert call_kwargs["poolclass"] == "queue"
    assert call_kwargs["pool_settings"] is mock_pool_settings
    assert call_kwargs["session_class"] is mock_session_class
    assert call_kwargs["expire_on_commit"] is True
    assert call_kwargs["connect_args"]["timeout"] == 30
    assert call_kwargs["isolation_level"] == "READ COMMITTED"
    assert call_kwargs["metrics"] is mock_metrics
    assert call_kwargs["on_engine_created"] is mock_callback
    assert call_kwargs["use_orjson"] is True
    assert call_kwargs["custom"] == "value"
    assert call_kwargs["dispose_timeout"] == 60.0


# ============================================================================
# AsyncSessionManagerBuilder - Reusability Tests
# ============================================================================


def test__async_session_manager_builder__reusable__builds_multiple_managers() -> None:
    # Arrange
    builder = AsyncSessionManagerBuilder("postgresql://localhost/test").with_pool("queue")

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        manager1 = builder.with_echo(True).build()
        manager2 = builder.with_echo(False).build()

    # Assert
    assert mock_manager_class.call_count == 2
    assert manager1 == mock_manager_class.return_value
    assert manager2 == mock_manager_class.return_value


def test__async_session_manager_builder__reusable__preserves_state() -> None:
    # Arrange
    builder = (
        AsyncSessionManagerBuilder("postgresql://localhost/test")
        .with_pool("queue")
        .with_isolation_level("SERIALIZABLE")
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.builder.AsyncSessionManager") as mock_manager_class:
        builder.with_echo(True).build()
        builder.with_echo(False).build()

    # Assert
    # Check second call
    call_kwargs = mock_manager_class.call_args_list[1][1]
    assert call_kwargs["poolclass"] == "queue"
    assert call_kwargs["isolation_level"] == "SERIALIZABLE"
    assert call_kwargs["echo"] is False
