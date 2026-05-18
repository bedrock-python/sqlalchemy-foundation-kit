"""Test models for integration tests."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_foundation_kit.base.models import Base, BaseTable, DatetimeColumnsMixin, UnConstrainedEnum

__all__ = ["Base", "Status", "TestOrder", "TestProduct", "TestUser"]


class Status(StrEnum):
    """Test status enum."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class TestUser(BaseTable, DatetimeColumnsMixin):
    """Test user model."""

    __tablename__ = "test_users"
    __test__ = False  # Tell pytest this is not a test class
    __created_at_index__ = True
    __updated_at_index__ = False

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    age: Mapped[int | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(UnConstrainedEnum(Status), default=Status.PENDING.value)
    user_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class TestProduct(BaseTable, DatetimeColumnsMixin):
    """Test product model."""

    __tablename__ = "test_products"
    __test__ = False

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column()
    quantity: Mapped[int] = mapped_column(default=0)


class TestOrder(BaseTable, DatetimeColumnsMixin):
    """Test order model."""

    __tablename__ = "test_orders"
    __test__ = False
    __created_at_index__ = True
    __updated_at_index__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column()
    product_id: Mapped[uuid.UUID] = mapped_column()
    quantity: Mapped[int] = mapped_column()
    total_price: Mapped[float] = mapped_column()
    status: Mapped[str] = mapped_column(UnConstrainedEnum(Status), default=Status.PENDING.value)
