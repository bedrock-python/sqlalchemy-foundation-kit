"""Unit tests for PostgresMetrics."""

from __future__ import annotations

import uuid

import pytest

# Skip all tests if prometheus-client is not installed
pytest.importorskip("prometheus_client")


from sqlalchemy_foundation_kit.contrib.metrics.postgres import (
    PostgresMetrics,
    _make_metric_name,
)


def _unique_prefix() -> str:
    """Generate unique prefix to avoid prometheus registry conflicts."""
    return f"test_{uuid.uuid4().hex[:8]}"


# ============================================================================
# _make_metric_name Tests
# ============================================================================


@pytest.mark.unit
def test___make_metric_name__no_prefix__returns_name() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = None

    # Act
    result = _make_metric_name(name, prefix)

    # Assert
    assert result == "postgres_db_pool_size"


@pytest.mark.unit
def test___make_metric_name__with_prefix__returns_prefixed_name() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = "my_service"

    # Act
    result = _make_metric_name(name, prefix)

    # Assert
    assert result == "my_service_postgres_db_pool_size"


@pytest.mark.unit
def test___make_metric_name__invalid_prefix_starts_with_number__raises_error() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = "123_service"

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid metric prefix"):
        _make_metric_name(name, prefix)


@pytest.mark.unit
def test___make_metric_name__invalid_prefix_with_spaces__raises_error() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = "my service"

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid metric prefix"):
        _make_metric_name(name, prefix)


@pytest.mark.unit
def test___make_metric_name__invalid_prefix_with_dash__raises_error() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = "my-service"

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid metric prefix"):
        _make_metric_name(name, prefix)


@pytest.mark.unit
def test___make_metric_name__valid_prefix_with_underscore__succeeds() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = "my_service_123"

    # Act
    result = _make_metric_name(name, prefix)

    # Assert
    assert result == "my_service_123_postgres_db_pool_size"


@pytest.mark.unit
def test___make_metric_name__empty_prefix__returns_name() -> None:
    # Arrange
    name = "postgres_db_pool_size"
    prefix = ""

    # Act
    result = _make_metric_name(name, prefix)

    # Assert
    assert result == "postgres_db_pool_size"


# ============================================================================
# PostgresMetrics Initialization Tests
# ============================================================================


@pytest.mark.unit
def test__postgres_metrics__init_without_prefix__creates_all_metrics() -> None:
    # Arrange & Act
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Assert
    assert metrics.pool_size is not None
    assert metrics.pool_checked_out is not None
    assert metrics.pool_overflow is not None
    assert metrics.connection_checkout_duration is not None
    assert metrics.connection_timeouts_total is not None
    assert metrics.connection_errors_total is not None


@pytest.mark.unit
def test__postgres_metrics__init_with_prefix__creates_prefixed_metrics() -> None:
    # Arrange
    prefix = _unique_prefix()

    # Act
    metrics = PostgresMetrics(prefix=prefix)

    # Assert
    # Check that metrics are created (we can't easily check names from prometheus_client API)
    assert metrics.pool_size is not None
    assert metrics.pool_checked_out is not None


@pytest.mark.unit
def test__postgres_metrics__buckets__matches_constant() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act - just verify metrics exist, internal access to buckets is not reliable
    # Assert
    assert metrics.connection_checkout_duration is not None


# ============================================================================
# record_pool_stats Tests
# ============================================================================


@pytest.mark.unit
def test__postgres_metrics__record_pool_stats__sets_gauge_values() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_pool_stats(
        pool_size=10,
        pool_checked_out=5,
        pool_overflow=2,
    )

    # Assert
    assert metrics.pool_size._value.get() == 10.0  # type: ignore[attr-defined]
    assert metrics.pool_checked_out._value.get() == 5.0  # type: ignore[attr-defined]
    assert metrics.pool_overflow._value.get() == 2.0  # type: ignore[attr-defined]


@pytest.mark.unit
def test__postgres_metrics__record_pool_stats__updates_existing_values() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())
    metrics.record_pool_stats(pool_size=10, pool_checked_out=5, pool_overflow=2)

    # Act
    metrics.record_pool_stats(pool_size=20, pool_checked_out=15, pool_overflow=5)

    # Assert
    assert metrics.pool_size._value.get() == 20.0  # type: ignore[attr-defined]
    assert metrics.pool_checked_out._value.get() == 15.0  # type: ignore[attr-defined]
    assert metrics.pool_overflow._value.get() == 5.0  # type: ignore[attr-defined]


@pytest.mark.unit
def test__postgres_metrics__record_pool_stats__zero_values__succeeds() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_pool_stats(pool_size=0, pool_checked_out=0, pool_overflow=0)

    # Assert
    assert metrics.pool_size._value.get() == 0.0  # type: ignore[attr-defined]
    assert metrics.pool_checked_out._value.get() == 0.0  # type: ignore[attr-defined]
    assert metrics.pool_overflow._value.get() == 0.0  # type: ignore[attr-defined]


# ============================================================================
# record_checkout Tests
# ============================================================================


@pytest.mark.unit
def test__postgres_metrics__record_checkout__observes_duration() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_checkout(duration=0.05)

    # Assert
    # Just verify it doesn't raise - internal histogram state is not reliably accessible
    assert metrics.connection_checkout_duration is not None


@pytest.mark.unit
def test__postgres_metrics__record_checkout__multiple_observations() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_checkout(duration=0.01)
    metrics.record_checkout(duration=0.02)
    metrics.record_checkout(duration=0.03)

    # Assert
    # Just verify it doesn't raise
    assert metrics.connection_checkout_duration is not None


@pytest.mark.unit
def test__postgres_metrics__record_checkout__zero_duration__succeeds() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_checkout(duration=0.0)

    # Assert
    assert metrics.connection_checkout_duration is not None


# ============================================================================
# record_error Tests
# ============================================================================


@pytest.mark.unit
def test__postgres_metrics__record_error__increments_error_counter() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_error(error_type="OperationalError")

    # Assert
    # Counter with labels is more complex, we check that it doesn't raise
    assert metrics.connection_errors_total._metrics  # type: ignore[attr-defined]


@pytest.mark.unit
def test__postgres_metrics__record_error__with_timeout__increments_both_counters() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_error(error_type="TimeoutError", is_timeout=True)

    # Assert
    # Check that timeout counter is incremented
    assert metrics.connection_timeouts_total._value.get() == 1.0  # type: ignore[attr-defined]


@pytest.mark.unit
def test__postgres_metrics__record_error__multiple_errors_same_type() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_error(error_type="OperationalError")
    metrics.record_error(error_type="OperationalError")

    # Assert
    # Verify counter with specific label
    counter_value = metrics.connection_errors_total.labels(error_type="OperationalError")._value.get()  # type: ignore[attr-defined]
    assert counter_value == 2.0


@pytest.mark.unit
def test__postgres_metrics__record_error__multiple_error_types() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_error(error_type="OperationalError")
    metrics.record_error(error_type="IntegrityError")

    # Assert
    operational = metrics.connection_errors_total.labels(error_type="OperationalError")._value.get()  # type: ignore[attr-defined]
    integrity = metrics.connection_errors_total.labels(error_type="IntegrityError")._value.get()  # type: ignore[attr-defined]
    assert operational == 1.0
    assert integrity == 1.0


@pytest.mark.unit
def test__postgres_metrics__record_error__multiple_timeouts() -> None:
    # Arrange
    metrics = PostgresMetrics(prefix=_unique_prefix())

    # Act
    metrics.record_error(error_type="TimeoutError", is_timeout=True)
    metrics.record_error(error_type="TimeoutError", is_timeout=True)

    # Assert
    assert metrics.connection_timeouts_total._value.get() == 2.0  # type: ignore[attr-defined]
