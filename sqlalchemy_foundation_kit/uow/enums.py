"""Enums for Unit of Work."""

from __future__ import annotations

from enum import StrEnum


class IsolationLevel(StrEnum):
    """PostgreSQL transaction isolation levels.

    Values match PostgreSQL's expected form (with spaces) for use with
    SQLAlchemy execution_options(isolation_level=...).
    """

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"
