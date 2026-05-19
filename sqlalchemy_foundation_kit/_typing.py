"""Shared type variables for the library.

Centralized location for all TypeVars to avoid duplication and ensure consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .uow.protocols import AsyncUowTransaction

__all__ = [
    "SessionT",
    "T",
    "T_co",
]

# Covariant TypeVar for UoW protocols (used in Protocol definitions)
T_co = TypeVar("T_co", bound="AsyncUowTransaction", covariant=True)

# Invariant TypeVar for UoW implementations
T = TypeVar("T", bound="AsyncUowTransaction")

# Session TypeVar for AsyncSessionManager and AsyncSessionManagerBuilder
SessionT = TypeVar("SessionT", bound="AsyncSession")
