"""Integration tests for session management."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.models import Status, TestUser

# ============================================================================
# Basic Session Operations Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__create_and_query__user_persisted(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(
        name="John Doe",
        email="john@example.com",
        age=30,
        status=Status.ACTIVE.value,
    )

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "john@example.com"))
    fetched_user = result.scalar_one_or_none()

    assert fetched_user is not None
    assert fetched_user.name == "John Doe"
    assert fetched_user.email == "john@example.com"
    assert fetched_user.age == 30
    assert fetched_user.status == Status.ACTIVE.value
    assert fetched_user.is_active is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__update__user_modified(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Jane", email="jane@example.com", age=25)

    async with async_session.begin():
        async_session.add(user)

    # Act
    async with async_session.begin():
        result = await async_session.execute(select(TestUser).where(TestUser.email == "jane@example.com"))
        user_to_update = result.scalar_one()
        user_to_update.age = 26
        user_to_update.status = Status.COMPLETED.value

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "jane@example.com"))
    updated_user = result.scalar_one()

    assert updated_user.age == 26
    assert updated_user.status == Status.COMPLETED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__delete__user_removed(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Delete Me", email="delete@example.com")

    async with async_session.begin():
        async_session.add(user)

    # Act
    async with async_session.begin():
        result = await async_session.execute(select(TestUser).where(TestUser.email == "delete@example.com"))
        user_to_delete = result.scalar_one()
        await async_session.delete(user_to_delete)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "delete@example.com"))
    deleted_user = result.scalar_one_or_none()

    assert deleted_user is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__rollback__changes_not_persisted(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Rollback Test", email="rollback@example.com")

    # Act
    try:
        async with async_session.begin():
            async_session.add(user)
            await async_session.flush()
            raise ValueError("Intentional error")
    except ValueError:
        pass

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "rollback@example.com"))
    fetched_user = result.scalar_one_or_none()

    assert fetched_user is None


# ============================================================================
# Multiple Records Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__bulk_insert__all_persisted(async_session: AsyncSession) -> None:
    # Arrange
    users = [TestUser(name=f"User {i}", email=f"user{i}@example.com", age=20 + i) for i in range(10)]

    # Act
    async with async_session.begin():
        async_session.add_all(users)

    # Assert
    result = await async_session.execute(select(TestUser))
    all_users = result.scalars().all()

    assert len(all_users) == 10
    assert all(user.name.startswith("User") for user in all_users)


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__query_with_filter__correct_results(async_session: AsyncSession) -> None:
    # Arrange
    users = [
        TestUser(name="Active User 1", email="active1@example.com", is_active=True),
        TestUser(name="Active User 2", email="active2@example.com", is_active=True),
        TestUser(name="Inactive User", email="inactive@example.com", is_active=False),
    ]

    async with async_session.begin():
        async_session.add_all(users)

    # Act
    result = await async_session.execute(select(TestUser).where(TestUser.is_active == True))  # noqa: E712
    active_users = result.scalars().all()

    # Assert
    assert len(active_users) == 2
    assert all(user.is_active for user in active_users)


# ============================================================================
# Transaction Isolation Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__nested_transaction__rollback_inner(async_session: AsyncSession) -> None:
    # Arrange
    outer_user = TestUser(name="Outer User", email="outer@example.com")

    # Act
    async with async_session.begin():
        async_session.add(outer_user)

        try:
            async with async_session.begin_nested():
                inner_user = TestUser(name="Inner User", email="inner@example.com")
                async_session.add(inner_user)
                raise ValueError("Rollback inner")
        except ValueError:
            pass

    # Assert
    result = await async_session.execute(select(TestUser))
    all_users = result.scalars().all()

    assert len(all_users) == 1
    assert all_users[0].email == "outer@example.com"


# ============================================================================
# UUID and Datetime Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__uuid_primary_key__generated_correctly(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="UUID Test", email="uuid@example.com")

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    assert isinstance(user.id, uuid.UUID)
    assert user.id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__datetime_columns__auto_populated(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="DateTime Test", email="datetime@example.com")

    # Act
    async with async_session.begin():
        async_session.add(user)
        await async_session.flush()

    # Assert
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.created_at == user.updated_at


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__updated_at__changes_on_update(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Update Time Test", email="updatetime@example.com")

    async with async_session.begin():
        async_session.add(user)
        await async_session.flush()
        original_updated_at = user.updated_at

    # Act
    async with async_session.begin():
        result = await async_session.execute(select(TestUser).where(TestUser.email == "updatetime@example.com"))
        user_to_update = result.scalar_one()
        user_to_update.name = "Updated Name"
        await async_session.flush()
        await async_session.refresh(user_to_update)
        new_updated_at = user_to_update.updated_at

    # Assert
    assert new_updated_at >= original_updated_at


# ============================================================================
# Enum Column Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__enum_column__stored_and_retrieved(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Enum Test", email="enum@example.com", status=Status.ACTIVE.value)

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "enum@example.com"))
    fetched_user = result.scalar_one()

    assert fetched_user.status == Status.ACTIVE.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__enum_default__applied_correctly(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="Enum Default Test", email="enumdefault@example.com")

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "enumdefault@example.com"))
    fetched_user = result.scalar_one()

    assert fetched_user.status == Status.PENDING.value


# ============================================================================
# JSONB Column Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__jsonb_column__stored_and_retrieved(async_session: AsyncSession) -> None:
    # Arrange
    user_metadata = {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}
    user = TestUser(name="JSONB Test", email="jsonb@example.com", user_metadata=user_metadata)

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "jsonb@example.com"))
    fetched_user = result.scalar_one()

    assert fetched_user.user_metadata == user_metadata
    assert fetched_user.user_metadata["key1"] == "value1"
    assert fetched_user.user_metadata["key2"] == 42


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__jsonb_default__empty_dict(async_session: AsyncSession) -> None:
    # Arrange
    user = TestUser(name="JSONB Default Test", email="jsonbdefault@example.com")

    # Act
    async with async_session.begin():
        async_session.add(user)

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == "jsonbdefault@example.com"))
    fetched_user = result.scalar_one()

    assert fetched_user.user_metadata == {}


# ============================================================================
# Unique Constraint Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__async_session__unique_constraint__violated_raises_error(async_session: AsyncSession) -> None:
    # Arrange
    user1 = TestUser(name="Duplicate Test 1", email="duplicate@example.com")
    user2 = TestUser(name="Duplicate Test 2", email="duplicate@example.com")

    async with async_session.begin():
        async_session.add(user1)

    # Act & Assert
    with pytest.raises(Exception):  # IntegrityError
        async with async_session.begin():
            async_session.add(user2)
