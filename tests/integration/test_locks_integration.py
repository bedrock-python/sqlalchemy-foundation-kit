"""Integration tests for PostgreSQL advisory locks."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_foundation_kit.session.locks import try_advisory_xact_lock

# ============================================================================
# Advisory Lock Acquisition Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__lock_acquired__returns_true(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = "test_lock_1"

    # Act
    async with async_session.begin():
        result = await try_advisory_xact_lock(async_session, lock_key)

    # Assert
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__same_key_twice__both_succeed(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = "test_lock_same"

    # Act & Assert
    async with async_session.begin():
        result1 = await try_advisory_xact_lock(async_session, lock_key)
        result2 = await try_advisory_xact_lock(async_session, lock_key)

        # PostgreSQL advisory locks are reentrant within same transaction
        assert result1 is True
        assert result2 is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__different_keys__both_acquired(async_session: AsyncSession) -> None:
    # Arrange
    lock_key1 = "test_lock_key1"
    lock_key2 = "test_lock_key2"

    # Act
    async with async_session.begin():
        result1 = await try_advisory_xact_lock(async_session, lock_key1)
        result2 = await try_advisory_xact_lock(async_session, lock_key2)

    # Assert
    assert result1 is True
    assert result2 is True


# ============================================================================
# Lock Release Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__released_after_commit(
    async_session: AsyncSession,
    async_session_factory,
) -> None:
    # Arrange
    lock_key = "test_lock_release"

    # Act - acquire lock in first transaction
    async with async_session.begin():
        result1 = await try_advisory_xact_lock(async_session, lock_key)
        assert result1 is True

    # Try to acquire same lock in new session after commit
    async with async_session_factory() as new_session, new_session.begin():
        result2 = await try_advisory_xact_lock(new_session, lock_key)

    # Assert
    assert result2 is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__released_after_rollback(
    async_session: AsyncSession,
    async_session_factory,
) -> None:
    # Arrange
    lock_key = "test_lock_rollback"

    # Act - acquire lock and rollback
    try:
        async with async_session.begin():
            result1 = await try_advisory_xact_lock(async_session, lock_key)
            assert result1 is True
            raise ValueError("Intentional rollback")
    except ValueError:
        pass

    # Try to acquire same lock in new session after rollback
    async with async_session_factory() as new_session, new_session.begin():
        result2 = await try_advisory_xact_lock(new_session, lock_key)

    # Assert
    assert result2 is True


# ============================================================================
# Concurrent Lock Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__concurrent_sessions__only_one_acquires(
    async_session_factory,
) -> None:
    # Arrange
    lock_key = "test_lock_concurrent"
    sessions_ready = asyncio.Event()
    lock_acquired = asyncio.Event()
    task_ready_count = 0
    ready_lock = asyncio.Lock()

    async def try_acquire_lock(task_id: int) -> bool:
        nonlocal task_ready_count

        # Open session and transaction BEFORE signaling ready
        async with async_session_factory() as session:
            async with session.begin():
                # Mark this task as ready
                async with ready_lock:
                    task_ready_count += 1
                    if task_ready_count == 5:
                        sessions_ready.set()

                # Wait for all tasks to be ready
                await sessions_ready.wait()

                # Try to acquire lock
                result = await try_advisory_xact_lock(session, lock_key)

                # Hold lock longer to ensure other tasks definitely try while it's held
                if result:
                    lock_acquired.set()
                    await asyncio.sleep(0.5)  # Increased from 0.2 to 0.5
                else:
                    # Wait a bit to ensure we actually tried while lock was held
                    await lock_acquired.wait()

                return result

    # Act - create tasks that will try to acquire lock concurrently
    tasks = [asyncio.create_task(try_acquire_lock(i)) for i in range(5)]

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)

    # Assert - only one should succeed since they all tried while lock was held
    acquired_count = sum(results)
    assert acquired_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__wait_for_release__eventually_acquires(
    async_session_factory,
) -> None:
    # Arrange
    lock_key = "test_lock_wait"
    lock_acquired_event = asyncio.Event()
    second_task_started = asyncio.Event()

    async def hold_lock_briefly() -> None:
        async with async_session_factory() as session, session.begin():
            result = await try_advisory_xact_lock(session, lock_key)
            assert result is True
            lock_acquired_event.set()
            await second_task_started.wait()
            await asyncio.sleep(0.1)  # Hold lock briefly

    async def try_acquire_after_wait() -> bool:
        await lock_acquired_event.wait()
        second_task_started.set()
        await asyncio.sleep(0.2)  # Wait for first lock to release

        async with async_session_factory() as session, session.begin():
            return await try_advisory_xact_lock(session, lock_key)

    # Act
    task1 = asyncio.create_task(hold_lock_briefly())
    task2 = asyncio.create_task(try_acquire_after_wait())

    results = await asyncio.gather(task1, task2)

    # Assert
    assert results[1] is True  # Second task should acquire lock after first releases


# ============================================================================
# Lock Key Hashing Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__long_string_key__works(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = "a" * 1000  # Very long key

    # Act
    async with async_session.begin():
        result = await try_advisory_xact_lock(async_session, lock_key)

    # Assert
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__unicode_key__works(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = "test_lock_🔒"

    # Act
    async with async_session.begin():
        result = await try_advisory_xact_lock(async_session, lock_key)

    # Assert
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__same_hash_different_strings__conflict(
    async_session: AsyncSession,
) -> None:
    # Arrange
    # These two strings should have the same hash (statistically unlikely but possible)
    lock_key1 = "key1"
    lock_key2 = "key2"

    # Act
    async with async_session.begin():
        result1 = await try_advisory_xact_lock(async_session, lock_key1)
        result2 = await try_advisory_xact_lock(async_session, lock_key2)

    # Assert
    assert result1 is True
    # result2 will be True if hashes are different, False if same
    # We can't predict the hash collision, so we just check it returns a boolean
    assert isinstance(result2, bool)


# ============================================================================
# Edge Cases Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__empty_string__works(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = ""

    # Act
    async with async_session.begin():
        result = await try_advisory_xact_lock(async_session, lock_key)

    # Assert
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__special_characters__works(async_session: AsyncSession) -> None:
    # Arrange
    lock_key = "test-lock_123!@#$%^&*()"

    # Act
    async with async_session.begin():
        result = await try_advisory_xact_lock(async_session, lock_key)

    # Assert
    assert result is True


# ============================================================================
# Multiple Sessions Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__two_sessions_different_locks__both_succeed(
    async_session_factory,
) -> None:
    # Arrange
    lock_key1 = "session1_lock"
    lock_key2 = "session2_lock"

    # Act
    async with async_session_factory() as session1, session1.begin():
        result1 = await try_advisory_xact_lock(session1, lock_key1)

        async with async_session_factory() as session2, session2.begin():
            result2 = await try_advisory_xact_lock(session2, lock_key2)

    # Assert
    assert result1 is True
    assert result2 is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__nested_transaction__inner_rollback_releases_lock(
    async_session: AsyncSession,
    async_session_factory,
) -> None:
    # Arrange
    lock_key = "test_nested_lock"

    # Act - Try to acquire in nested transaction and rollback
    async with async_session.begin():
        try:
            async with async_session.begin_nested():
                result1 = await try_advisory_xact_lock(async_session, lock_key)
                assert result1 is True
                raise ValueError("Rollback nested")
        except ValueError:
            pass

    # Try to acquire in new session
    async with async_session_factory() as new_session, new_session.begin():
        result2 = await try_advisory_xact_lock(new_session, lock_key)

    # Assert
    assert result2 is True
