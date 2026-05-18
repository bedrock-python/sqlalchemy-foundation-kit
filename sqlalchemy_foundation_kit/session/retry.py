"""Retry utilities for database connection startup."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_HEALTHCHECK_QUERY = "SELECT 1"


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry behavior with exponential backoff.

    Attributes:
        max_retries: Maximum number of attempts before giving up.
        retry_delay: Base delay in seconds; actual delay is ``retry_delay * 2 ** attempt``,
            capped at ``max_backoff_delay``.
        max_backoff_delay: Maximum delay between retries in seconds.
            Prevents exponential backoff from growing indefinitely.
    """

    max_retries: int = 3
    retry_delay: float = 1.0
    max_backoff_delay: float = 60.0


DEFAULT_RETRY_CONFIG = RetryConfig()


async def retry_async_connection(
    connect_func: Callable[[], Awaitable[None]],
    service_name: str,
    config: RetryConfig = DEFAULT_RETRY_CONFIG,
) -> None:
    """Retry an async connection callable with exponential backoff.

    Args:
        connect_func: Callable that attempts to establish/test the connection.
        service_name: Human-readable service name used in log messages.
        config: Retry behavior configuration.

    Raises:
        Exception: Re-raises the last exception when all attempts fail.
    """
    for attempt in range(config.max_retries):
        try:
            await connect_func()
        except Exception:
            if attempt == config.max_retries - 1:
                logger.exception("%s connection failed after %d attempts", service_name, config.max_retries)
                raise
            logger.warning("%s connection attempt %d failed, retrying...", service_name, attempt + 1)
            delay = min(config.retry_delay * (2**attempt), config.max_backoff_delay)
            await asyncio.sleep(delay)
        else:
            logger.info("%s connection successful", service_name)
            return


__all__ = [
    "DEFAULT_HEALTHCHECK_QUERY",
    "DEFAULT_RETRY_CONFIG",
    "RetryConfig",
    "retry_async_connection",
]
