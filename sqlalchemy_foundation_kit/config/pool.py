"""Connection pool configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoolConfig:
    """Connection pool configuration."""

    size: int | None = None
    max_overflow: int | None = None
    pre_ping: bool = True
    recycle: int | None = None
    timeout: float | None = None
