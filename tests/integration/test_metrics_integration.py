"""Integration tests for the connection pool metrics, against a pool that runs out."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_foundation_kit.session.manager import AsyncSessionManager
from tests.integration.conftest import PostgresContainer, asyncpg_url

POOL_TIMEOUT_SECONDS = 0.5
SHORT_HOLD_SECONDS = 0.25  # shorter than the timeout: whoever queues behind it is served
LONG_HOLD_SECONDS = 0.9  # longer: whoever queues behind it gives up


@dataclass
class _PoolSettings:
    """One connection, no overflow, a short checkout timeout — a pool that runs out."""

    kind: str = "async_adapted_queue"
    size: int = 1
    max_overflow: int = 0
    pre_ping: bool = False
    recycle: int = -1
    timeout: float = POOL_TIMEOUT_SECONDS


class _RecordingMetrics:
    """Keeps every recorded value, so a test can compare the wait against the hold."""

    def __init__(self) -> None:
        self.waits: list[tuple[float, bool]] = []
        self.held: list[float] = []

    def record_pool_stats(self, pool_size: int, pool_checked_out: int, pool_overflow: int) -> None: ...

    def record_checkout(self, duration: float) -> None:
        self.held.append(duration)

    def record_checkout_wait(self, duration: float, timed_out: bool = False) -> None:
        self.waits.append((duration, timed_out))

    def record_error(self, error_type: str, is_timeout: bool = False) -> None: ...

    def reset(self) -> None:
        self.waits.clear()
        self.held.clear()

    @property
    def served_waits(self) -> list[float]:
        return [duration for duration, gave_up in self.waits if not gave_up]

    @property
    def timed_out_waits(self) -> list[float]:
        return [duration for duration, gave_up in self.waits if gave_up]


async def _holds_the_connection(manager: AsyncSessionManager[AsyncSession], seconds: float) -> None:
    """Take the pool's only connection and sit on it, without asking the server to wait."""
    async with manager.get_session() as session:
        await session.execute(text("SELECT 1"))
        await asyncio.sleep(seconds)


async def _queues_behind_it(manager: AsyncSessionManager[AsyncSession]) -> None:
    """Ask for a connection while the holder has it, then give it straight back."""
    await asyncio.sleep(0.05)
    async with manager.get_session() as session:
        await session.execute(text("SELECT 1"))


async def _gives_up(manager: AsyncSessionManager[AsyncSession]) -> None:
    """Ask for a connection that never comes and fail the way the reporter's callers did."""
    await asyncio.sleep(0.05)
    with pytest.raises(SATimeoutError):
        async with manager.get_session() as session:
            await session.execute(text("SELECT 1"))


async def _warm(manager: AsyncSessionManager[AsyncSession]) -> None:
    """Pay for the connect handshake up front, so later waits are the queue wait alone."""
    async with manager.get_session() as session:
        await session.execute(text("SELECT 1"))


@pytest.fixture
async def recording_manager(
    postgres_container: PostgresContainer,
) -> AsyncIterator[tuple[AsyncSessionManager[AsyncSession], _RecordingMetrics]]:
    metrics = _RecordingMetrics()
    manager: AsyncSessionManager[AsyncSession] = AsyncSessionManager(
        asyncpg_url(postgres_container),
        poolclass="async_adapted_queue",
        metrics=metrics,
        pool_settings=_PoolSettings(),
    )
    await _warm(manager)
    metrics.reset()
    yield manager, metrics
    await manager.aclose()


# ============================================================================
# Pool Checkout Wait and Timeout Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__pool_metrics__pool_runs_out__counts_the_timeout_and_measures_the_wait(
    recording_manager: tuple[AsyncSessionManager[AsyncSession], _RecordingMetrics],
) -> None:
    # Arrange: the reporter's shape with one connection instead of four — eight workers
    # against a pool of four tells the same story with more noise. Two runs: one where the
    # caller behind the holder is served, one where it gives up.
    manager, metrics = recording_manager

    # Act: the holder keeps the only connection for less than the pool timeout.
    await asyncio.gather(
        _holds_the_connection(manager, SHORT_HOLD_SECONDS),
        _queues_behind_it(manager),
    )

    # Assert: one caller took the connection straight away, the other sat in the queue for
    # most of the first one's hold. That is a wait — and it is the mirror image of what the
    # checkin listener sees, where the caller that waited longest held it for no time at
    # all. Reading one off the other is the mistake the single old histogram invited.
    assert len(metrics.waits) == 2, "the pool recorded no checkout wait at all"
    assert metrics.timed_out_waits == []
    assert min(metrics.served_waits) < SHORT_HOLD_SECONDS / 2
    assert max(metrics.served_waits) >= SHORT_HOLD_SECONDS / 2
    assert max(metrics.held) >= SHORT_HOLD_SECONDS * 0.8
    assert min(metrics.held) < SHORT_HOLD_SECONDS / 2

    # Arrange: now the holder keeps it for longer than the pool timeout.
    metrics.reset()

    # Act
    await asyncio.gather(
        _holds_the_connection(manager, LONG_HOLD_SECONDS),
        _gives_up(manager),
    )

    # Assert: the pool TimeoutError is raised before any DBAPI call, so it never reaches
    # the engine's handle_error listener. This is the only place it is counted, and the
    # counter the reporter watched stay at zero moves by exactly one.
    assert len(metrics.timed_out_waits) == 1
    assert metrics.timed_out_waits[0] == pytest.approx(POOL_TIMEOUT_SECONDS, abs=0.2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test__postgres_metrics__pool_runs_out__moves_the_series_a_dashboard_scrapes(
    postgres_container: PostgresContainer,
) -> None:
    # Arrange: the same run read the way an application reads it — off the Prometheus
    # registry, by name.
    pytest.importorskip("prometheus_client")
    from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics

    prefix = f"it_{uuid.uuid4().hex[:8]}"
    manager: AsyncSessionManager[AsyncSession] = AsyncSessionManager(
        asyncpg_url(postgres_container),
        poolclass="async_adapted_queue",
        metrics=PostgresMetrics(prefix=prefix),
        pool_settings=_PoolSettings(),
    )

    async with manager:
        # Act
        await asyncio.gather(
            _holds_the_connection(manager, LONG_HOLD_SECONDS),
            _gives_up(manager),
        )

    # Assert
    exposed = _exposed(prefix)
    assert exposed[f"{prefix}_postgres_db_connection_timeouts_total"] == 1.0
    assert exposed[f"{prefix}_postgres_db_connection_checkout_wait_seconds_count"] == 2.0
    assert exposed[f"{prefix}_postgres_db_connection_checkout_wait_seconds_sum"] >= POOL_TIMEOUT_SECONDS
    assert exposed[f"{prefix}_postgres_db_connection_held_duration_seconds_sum"] >= LONG_HOLD_SECONDS * 0.8
    # The old name keeps its data for one more minor release.
    assert (
        exposed[f"{prefix}_postgres_db_connection_checkout_duration_seconds_sum"]
        == exposed[f"{prefix}_postgres_db_connection_held_duration_seconds_sum"]
    )


def _exposed(prefix: str) -> dict[str, float]:
    """Read the sample values Prometheus would scrape for one metrics prefix."""
    from prometheus_client import REGISTRY, generate_latest

    samples: dict[str, float] = {}
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith(f"{prefix}_"):
            name, value = line.rsplit(" ", 1)
            samples[name] = float(value)
    return samples


# ============================================================================
# Pool Gauges Tests
# ============================================================================


@dataclass
class _GrowingPoolSettings:
    """Ten connections that can grow by twenty: the defaults, with a pool to watch."""

    kind: str = "async_adapted_queue"
    size: int = 10
    max_overflow: int = 20
    pre_ping: bool = False
    recycle: int = -1
    timeout: float = 5.0


async def _while_holding(manager: AsyncSessionManager[AsyncSession], n: int, prefix: str) -> dict[str, float]:
    """Check out ``n`` connections at once, read the registry while all are held, release them."""
    all_checked_out, release = asyncio.Event(), asyncio.Event()
    ready = 0

    async def one() -> None:
        nonlocal ready
        async with manager.get_session() as session:
            await session.execute(text("SELECT 1"))
            ready += 1
            if ready == n:
                all_checked_out.set()
            await release.wait()

    tasks = [asyncio.create_task(one()) for _ in range(n)]
    await all_checked_out.wait()
    exposed = _exposed(prefix)
    release.set()
    await asyncio.gather(*tasks)
    return exposed


def _gauges(exposed: dict[str, float], prefix: str) -> tuple[float, float, float]:
    """``(pool_size, pool_checked_out, pool_overflow)`` as scraped."""
    return (
        exposed[f"{prefix}_postgres_db_pool_size"],
        exposed[f"{prefix}_postgres_db_pool_checked_out"],
        exposed[f"{prefix}_postgres_db_pool_overflow"],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test__postgres_metrics__pool_gauges__describe_the_pool_while_busy_and_once_idle(
    postgres_container: PostgresContainer,
) -> None:
    # Arrange: the reporter's run -- size=10, max_overflow=20, one request, then a burst of 12
    pytest.importorskip("prometheus_client")
    from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics

    prefix = f"it_{uuid.uuid4().hex[:8]}"
    manager: AsyncSessionManager[AsyncSession] = AsyncSessionManager(
        asyncpg_url(postgres_container),
        poolclass="async_adapted_queue",
        metrics=PostgresMetrics(prefix=prefix),
        pool_settings=_GrowingPoolSettings(),
    )

    async with manager:
        # Act & Assert: one connection in use is not "-9 overflow"
        assert _gauges(await _while_holding(manager, 1, prefix), prefix) == (10.0, 1.0, 0.0)
        # ...and once it is back, nothing is in use
        assert _gauges(_exposed(prefix), prefix) == (10.0, 0.0, 0.0)

        # Act & Assert: twelve at once is two past pool_size
        assert _gauges(await _while_holding(manager, 12, prefix), prefix) == (10.0, 12.0, 2.0)
        # ...and after the burst the overflow connections are closed and nothing is in use
        assert _gauges(_exposed(prefix), prefix) == (10.0, 0.0, 0.0)


# ============================================================================
# What Counts as a Connection Timeout Tests
# ============================================================================


def _connection_series(prefix: str) -> tuple[float, float, float]:
    """``(timeouts, errors over all labels, checkout waits)`` as scraped."""
    exposed = _exposed(prefix)
    errors = sum(v for k, v in exposed.items() if k.startswith(f"{prefix}_postgres_db_connection_errors_total{{"))
    return (
        exposed[f"{prefix}_postgres_db_connection_timeouts_total"],
        errors,
        exposed[f"{prefix}_postgres_db_connection_checkout_wait_seconds_count"],
    )


def _error_types(prefix: str) -> set[str]:
    """The ``error_type`` labels ``connection_errors_total`` has seen."""
    marker = f'{prefix}_postgres_db_connection_errors_total{{error_type="'
    return {k[len(marker) :].split('"', 1)[0] for k in _exposed(prefix) if k.startswith(marker)}


def _metrics_manager(url: str, prefix: str, connect_args: dict[str, object]) -> AsyncSessionManager[AsyncSession]:
    from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics

    return AsyncSessionManager(
        url,
        poolclass="async_adapted_queue",
        metrics=PostgresMetrics(prefix=prefix),
        pool_settings=_PoolSettings(size=2, timeout=5.0),
        connect_args=connect_args,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test__postgres_metrics__statement_timeout__is_not_a_connection_timeout(
    postgres_container: PostgresContainer,
) -> None:
    # Arrange: asyncpg's command_timeout fires on a running statement; the pool never waited
    pytest.importorskip("prometheus_client")
    prefix = f"it_{uuid.uuid4().hex[:8]}"
    manager = _metrics_manager(asyncpg_url(postgres_container), prefix, {"command_timeout": 0.1})

    # Act
    async with manager:
        with pytest.raises(TimeoutError):
            async with manager.get_session() as session:
                await session.execute(text("SELECT pg_sleep(1)"))

    # Assert
    timeouts, errors, waits = _connection_series(prefix)
    assert timeouts == 0.0
    assert _error_types(prefix) == {"TimeoutError"}
    assert (errors, waits) == (1.0, 1.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test__postgres_metrics__connect_timeout__counts_a_connection_timeout_and_its_wait() -> None:
    # Arrange: a server that accepts the TCP connection and never answers the startup packet
    pytest.importorskip("prometheus_client")

    async def silent(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read()  # until the client gives up and closes
        writer.close()

    server = await asyncio.start_server(silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    prefix = f"it_{uuid.uuid4().hex[:8]}"
    manager = _metrics_manager(f"postgresql+asyncpg://u:p@127.0.0.1:{port}/db", prefix, {"timeout": 0.3})

    # Act
    async with server, manager:
        with pytest.raises(TimeoutError):
            async with manager.get_session() as session:
                await session.execute(text("SELECT 1"))

    # Assert
    timeouts, errors, waits = _connection_series(prefix)
    assert (timeouts, errors, waits) == (1.0, 0.0, 1.0)
    assert _exposed(prefix)[f"{prefix}_postgres_db_connection_checkout_wait_seconds_sum"] >= 0.3


@pytest.mark.integration
@pytest.mark.asyncio
async def test__postgres_metrics__connection_refused__counts_an_error_and_its_wait() -> None:
    # Arrange: a port nothing listens on
    pytest.importorskip("prometheus_client")
    server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    prefix = f"it_{uuid.uuid4().hex[:8]}"
    manager = _metrics_manager(f"postgresql+asyncpg://u:p@127.0.0.1:{port}/db", prefix, {})

    # Act
    async with manager:
        with pytest.raises(OSError):
            async with manager.get_session() as session:
                await session.execute(text("SELECT 1"))

    # Assert
    timeouts, errors, waits = _connection_series(prefix)
    assert (timeouts, errors, waits) == (0.0, 1.0, 1.0)
    assert _error_types(prefix) == {"ConnectionRefusedError"}
