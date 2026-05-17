"""Protocols for database infrastructure.

This module defines protocols (structural subtyping) for key abstractions,
allowing dependency inversion without tight coupling to specific implementations.
"""

from __future__ import annotations

from .metrics import (
    CheckoutRecorder,
    ErrorRecorder,
    PoolStatsRecorder,
    PostgresMetricsProtocol,
)

__all__ = [
    "CheckoutRecorder",
    "ErrorRecorder",
    "PoolStatsRecorder",
    "PostgresMetricsProtocol",
]
