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
