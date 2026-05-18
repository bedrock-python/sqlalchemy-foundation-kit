"""Unit tests for SQLAlchemy engine configuration utilities."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.pool import (
    AsyncAdaptedQueuePool,
    FallbackAsyncAdaptedQueuePool,
    NullPool,
    QueuePool,
    SingletonThreadPool,
    StaticPool,
)

from sqlalchemy_foundation_kit.base.engine import (
    PoolRegistry,
    build_engine_kwargs,
    register_pool_class,
    resolve_pool_class,
)

# ============================================================================
# PoolRegistry.resolve Tests
# ============================================================================


def test__pool_registry_resolve__null_pool__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("null")

    # Assert
    assert pool_class == NullPool


def test__pool_registry_resolve__queue_pool__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("queue")

    # Assert
    assert pool_class == QueuePool


def test__pool_registry_resolve__singleton_thread__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("singleton_thread")

    # Assert
    assert pool_class == SingletonThreadPool


def test__pool_registry_resolve__async_adapted_queue__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("async_adapted_queue")

    # Assert
    assert pool_class == AsyncAdaptedQueuePool


def test__pool_registry_resolve__fallback_async_adapted__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("fallback_async_adapted_queue")

    # Assert
    assert pool_class == FallbackAsyncAdaptedQueuePool


def test__pool_registry_resolve__static__returns_class() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("static")

    # Assert
    assert pool_class == StaticPool


def test__pool_registry_resolve__case_insensitive__works() -> None:
    # Arrange & Act
    pool_class = PoolRegistry.resolve("NULL")

    # Assert
    assert pool_class == NullPool


def test__pool_registry_resolve__unknown_pool__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError) as exc_info:
        PoolRegistry.resolve("unknown_pool")

    assert "Unknown pool class: unknown_pool" in str(exc_info.value)
    assert "Available:" in str(exc_info.value)


# ============================================================================
# PoolRegistry.list_available Tests
# ============================================================================


def test__pool_registry_list_available__returns_sorted_list() -> None:
    # Arrange & Act
    available = PoolRegistry.list_available()

    # Assert
    assert isinstance(available, list)
    assert len(available) >= 6
    assert available == sorted(available)


def test__pool_registry_list_available__includes_builtin_pools() -> None:
    # Arrange & Act
    available = PoolRegistry.list_available()

    # Assert
    assert "null" in available
    assert "queue" in available
    assert "async_adapted_queue" in available


# ============================================================================
# PoolRegistry.register Tests
# ============================================================================


def test__pool_registry_register__new_pool__succeeds() -> None:
    # Arrange
    class CustomPool(QueuePool):
        pass

    # Act
    PoolRegistry.register("test_custom_pool_1", CustomPool)

    # Assert
    assert PoolRegistry.resolve("test_custom_pool_1") == CustomPool


def test__pool_registry_register__duplicate_without_override__raises_error() -> None:
    # Arrange
    class AnotherPool(QueuePool):
        pass

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        PoolRegistry.register("null", AnotherPool)

    assert "already registered" in str(exc_info.value)
    assert "override=True" in str(exc_info.value)


def test__pool_registry_register__duplicate_with_override__succeeds() -> None:
    # Arrange
    class OverridePool(QueuePool):
        pass

    original = PoolRegistry.resolve("queue")

    # Act
    PoolRegistry.register("queue", OverridePool, override=True)

    # Assert
    assert PoolRegistry.resolve("queue") == OverridePool

    # Cleanup
    PoolRegistry.register("queue", original, override=True)


def test__pool_registry_register__mixed_case_name__resolves_case_insensitive() -> None:
    # Arrange
    class MixedPool(QueuePool):
        pass

    # Act
    PoolRegistry.register("test_mixed_pool", MixedPool)

    # Assert
    assert PoolRegistry.resolve("test_mixed_pool") == MixedPool
    assert PoolRegistry.resolve("TEST_MIXED_POOL") == MixedPool


# ============================================================================
# resolve_pool_class Tests
# ============================================================================


def test__resolve_pool_class__string_name__returns_class() -> None:
    # Arrange & Act
    pool_class = resolve_pool_class("null")

    # Assert
    assert pool_class == NullPool


def test__resolve_pool_class__literal_type__returns_class() -> None:
    # Arrange & Act
    pool_class = resolve_pool_class("async_adapted_queue")

    # Assert
    assert pool_class == AsyncAdaptedQueuePool


def test__resolve_pool_class__class_type__returns_same() -> None:
    # Arrange
    custom_pool = QueuePool

    # Act
    pool_class = resolve_pool_class(custom_pool)

    # Assert
    assert pool_class is custom_pool


def test__resolve_pool_class__unknown_string__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError):
        resolve_pool_class("nonexistent")


def test__resolve_pool_class__mixed_case__works() -> None:
    # Arrange & Act
    pool_class = resolve_pool_class("Async_Adapted_Queue")

    # Assert
    assert pool_class == AsyncAdaptedQueuePool


# ============================================================================
# register_pool_class Tests
# ============================================================================


def test__register_pool_class__new_pool__registers() -> None:
    # Arrange
    class ConveniencePool(QueuePool):
        pass

    # Act
    register_pool_class("convenience_pool_test", ConveniencePool)

    # Assert
    assert PoolRegistry.resolve("convenience_pool_test") == ConveniencePool


def test__register_pool_class__with_override__works() -> None:
    # Arrange
    class OverrideTest(QueuePool):
        pass

    original = PoolRegistry.resolve("static")

    # Act
    register_pool_class("static", OverrideTest, override=True)

    # Assert
    assert PoolRegistry.resolve("static") == OverrideTest

    # Cleanup
    register_pool_class("static", original, override=True)


# ============================================================================
# build_engine_kwargs - Basic Tests
# ============================================================================


def test__build_engine_kwargs__minimal_config__returns_basic() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
        use_orjson=False,
    )

    # Assert
    assert kwargs["echo"] is False
    assert kwargs["poolclass"] == NullPool
    assert kwargs["isolation_level"] is None
    assert kwargs["pool_pre_ping"] is True


def test__build_engine_kwargs__echo_true__sets_echo() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=True,
        poolclass=QueuePool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert kwargs["echo"] is True


def test__build_engine_kwargs__isolation_level__sets_value() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=QueuePool,
        isolation_level="READ COMMITTED",
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert kwargs["isolation_level"] == "READ COMMITTED"


# ============================================================================
# build_engine_kwargs - Pool Settings Tests
# ============================================================================


def test__build_engine_kwargs__pool_settings__applies_config() -> None:
    # Arrange
    pool_settings = Mock()
    pool_settings.pre_ping = False
    pool_settings.size = 20
    pool_settings.max_overflow = 10
    pool_settings.recycle = 3600
    pool_settings.timeout = 30.0

    # Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=QueuePool,
        isolation_level=None,
        pool_settings=pool_settings,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert kwargs["pool_pre_ping"] is False
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_recycle"] == 3600
    assert kwargs["pool_timeout"] == 30.0


def test__build_engine_kwargs__pool_settings_none_values__skips_none() -> None:
    # Arrange
    pool_settings = Mock()
    pool_settings.pre_ping = True
    pool_settings.size = None
    pool_settings.max_overflow = None
    pool_settings.recycle = None
    pool_settings.timeout = None

    # Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=QueuePool,
        isolation_level=None,
        pool_settings=pool_settings,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert "pool_size" not in kwargs
    assert "max_overflow" not in kwargs
    assert "pool_recycle" not in kwargs
    assert "pool_timeout" not in kwargs


# ============================================================================
# build_engine_kwargs - Connect Args Tests
# ============================================================================


def test__build_engine_kwargs__connect_args__includes_args() -> None:
    # Arrange
    connect_args = {
        "server_settings": {"jit": "off"},
        "timeout": 10,
    }

    # Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=connect_args,
        extra_kwargs={},
    )

    # Assert
    assert "connect_args" in kwargs
    assert kwargs["connect_args"]["timeout"] == 10


def test__build_engine_kwargs__connect_args_with_none__filters_none() -> None:
    # Arrange
    connect_args = {
        "timeout": 10,
        "ssl": None,
        "server_settings": {"jit": "off"},
    }

    # Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=connect_args,
        extra_kwargs={},
    )

    # Assert
    assert "ssl" not in kwargs["connect_args"]
    assert kwargs["connect_args"]["timeout"] == 10


def test__build_engine_kwargs__empty_connect_args_with_none__filters() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args={"key": None},
        extra_kwargs={},
    )

    # Assert
    assert kwargs["connect_args"] == {}


# ============================================================================
# build_engine_kwargs - Extra Kwargs Tests
# ============================================================================


def test__build_engine_kwargs__extra_kwargs__includes_extra() -> None:
    # Arrange
    extra_kwargs = {
        "execution_options": {"statement_timeout": 5000},
        "logging_name": "my_engine",
    }

    # Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=QueuePool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs=extra_kwargs,
    )

    # Assert
    assert kwargs["execution_options"]["statement_timeout"] == 5000
    assert kwargs["logging_name"] == "my_engine"


def test__build_engine_kwargs__empty_extra_kwargs__no_error() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert "echo" in kwargs
    assert "poolclass" in kwargs


# ============================================================================
# build_engine_kwargs - Orjson Tests
# ============================================================================


def test__build_engine_kwargs__use_orjson_true__adds_config() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.base.serialization.configure_orjson_serialization") as mock_config:
        mock_config.return_value = {
            "json_serializer": "mock_serializer",
            "json_deserializer": "mock_deserializer",
        }

        # Act
        kwargs = build_engine_kwargs(
            echo=False,
            poolclass=NullPool,
            isolation_level=None,
            pool_settings=None,
            connect_args=None,
            extra_kwargs={},
            use_orjson=True,
        )

        # Assert
        mock_config.assert_called_once()
        assert kwargs["json_serializer"] == "mock_serializer"
        assert kwargs["json_deserializer"] == "mock_deserializer"


def test__build_engine_kwargs__use_orjson_false__no_config() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
        use_orjson=False,
    )

    # Assert
    assert "json_serializer" not in kwargs
    assert "json_deserializer" not in kwargs


# ============================================================================
# build_engine_kwargs - Integration Tests
# ============================================================================


def test__build_engine_kwargs__complex_config__combines_all() -> None:
    # Arrange
    pool_settings = Mock()
    pool_settings.pre_ping = True
    pool_settings.size = 15
    pool_settings.max_overflow = 5
    pool_settings.recycle = 1800
    pool_settings.timeout = 20.0

    connect_args = {"timeout": 30}
    extra_kwargs = {"echo_pool": True}

    # Act
    kwargs = build_engine_kwargs(
        echo=True,
        poolclass=AsyncAdaptedQueuePool,
        isolation_level="SERIALIZABLE",
        pool_settings=pool_settings,
        connect_args=connect_args,
        extra_kwargs=extra_kwargs,
    )

    # Assert
    assert kwargs["echo"] is True
    assert kwargs["poolclass"] == AsyncAdaptedQueuePool
    assert kwargs["isolation_level"] == "SERIALIZABLE"
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 15
    assert kwargs["connect_args"]["timeout"] == 30
    assert kwargs["echo_pool"] is True


def test__build_engine_kwargs__all_none__returns_minimal() -> None:
    # Arrange & Act
    kwargs = build_engine_kwargs(
        echo=False,
        poolclass=NullPool,
        isolation_level=None,
        pool_settings=None,
        connect_args=None,
        extra_kwargs={},
    )

    # Assert
    assert len(kwargs) == 4  # echo, poolclass, isolation_level, pool_pre_ping
    assert "pool_size" not in kwargs
    assert "connect_args" not in kwargs
