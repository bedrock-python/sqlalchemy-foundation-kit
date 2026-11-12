"""Integration tests for DatetimeColumnsMixin against a real PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.models import TestUser

# Not UTC, and no daylight saving time since 2014, so the offset is the same all year.
SESSION_TIME_ZONE = "Europe/Moscow"


@pytest.mark.integration
@pytest.mark.asyncio
async def test__datetime_mixin__non_utc_session__defaults_are_insert_instant(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    async with async_session_factory() as session, session.begin():
        await session.execute(text(f"SET LOCAL TIME ZONE '{SESSION_TIME_ZONE}'"))
        user = TestUser(name="Ann", email="ann@example.com")

        # Act
        session.add(user)
        await session.flush()
        await session.refresh(user)
        transaction_start = (await session.execute(select(func.now()))).scalar_one()

    # Assert
    assert user.created_at == transaction_start
    assert user.updated_at == transaction_start


@pytest.mark.integration
@pytest.mark.asyncio
async def test__datetime_mixin__non_utc_session__updated_at_is_update_instant(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    async with async_session_factory() as session:
        async with session.begin():
            user = TestUser(name="Ann", email="ann@example.com")
            session.add(user)

        # Act
        async with session.begin():
            await session.execute(text(f"SET LOCAL TIME ZONE '{SESSION_TIME_ZONE}'"))
            user.name = "Bob"
            await session.flush()
            await session.refresh(user)
            transaction_start = (await session.execute(select(func.now()))).scalar_one()

    # Assert
    assert user.updated_at == transaction_start
