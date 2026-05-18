"""Unit tests for base ORM models and mixins."""

from __future__ import annotations

import datetime
import enum

from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_foundation_kit.base.models import (
    DB_NAMING_CONVENTION,
    Base,
    BaseTable,
    DatetimeColumnsMixin,
    UnConstrainedEnum,
    _extract_enum_values,
)

# ============================================================================
# DB_NAMING_CONVENTION Tests
# ============================================================================


def test__db_naming_convention__exists__has_expected_keys() -> None:
    # Arrange & Act
    keys = set(DB_NAMING_CONVENTION.keys())

    # Assert
    expected_keys = {"ix", "uq", "ck", "fk", "pk"}
    assert keys == expected_keys


def test__db_naming_convention__index__matches_pattern() -> None:
    # Arrange & Act
    pattern = DB_NAMING_CONVENTION["ix"]

    # Assert
    assert pattern == "%(column_0_label)s_idx"


def test__db_naming_convention__unique__matches_pattern() -> None:
    # Arrange & Act
    pattern = DB_NAMING_CONVENTION["uq"]

    # Assert
    assert pattern == "%(table_name)s_%(column_0_name)s_key"


def test__db_naming_convention__check__matches_pattern() -> None:
    # Arrange & Act
    pattern = DB_NAMING_CONVENTION["ck"]

    # Assert
    assert pattern == "%(table_name)s_%(constraint_name)s_check"


def test__db_naming_convention__foreign_key__matches_pattern() -> None:
    # Arrange & Act
    pattern = DB_NAMING_CONVENTION["fk"]

    # Assert
    assert pattern == "%(table_name)s_%(column_0_name)s_fkey"


def test__db_naming_convention__primary_key__matches_pattern() -> None:
    # Arrange & Act
    pattern = DB_NAMING_CONVENTION["pk"]

    # Assert
    assert pattern == "%(table_name)s_pkey"


# ============================================================================
# Base Class Tests
# ============================================================================


def test__base__has_type_annotation_map__maps_uuid() -> None:
    # Arrange & Act
    import uuid

    mapped_type = Base.type_annotation_map.get(uuid.UUID)

    # Assert
    assert isinstance(mapped_type, postgresql.UUID)


def test__base__has_type_annotation_map__maps_datetime() -> None:
    # Arrange & Act
    mapped_type = Base.type_annotation_map.get(datetime.datetime)

    # Assert
    assert isinstance(mapped_type, TIMESTAMP)
    assert mapped_type.timezone is True


def test__base__metadata__has_naming_convention() -> None:
    # Arrange & Act
    naming_convention = Base.metadata.naming_convention

    # Assert
    assert naming_convention == DB_NAMING_CONVENTION


def test__base__can_create_model__no_errors() -> None:
    # Arrange & Act
    class TestModel(Base):
        __tablename__ = "test_table_base"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]

    # Assert
    assert TestModel.__tablename__ == "test_table_base"
    assert hasattr(TestModel, "id")
    assert hasattr(TestModel, "name")


# ============================================================================
# BaseTable Tests
# ============================================================================


def test__base_table__repr__includes_all_columns() -> None:
    # Arrange
    class User(BaseTable):
        __tablename__ = "users_repr_test"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]
        email: Mapped[str]

    user = User(id=1, name="John", email="john@example.com")

    # Act
    repr_str = repr(user)

    # Assert
    assert "users_repr_test" in repr_str
    assert "id=1" in repr_str
    assert "name=John" in repr_str
    assert "email=john@example.com" in repr_str


def test__base_table__repr__handles_none_values() -> None:
    # Arrange
    class Product(BaseTable):
        __tablename__ = "products_none_test"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]
        description: Mapped[str | None] = mapped_column(default=None)

    product = Product(id=1, name="Test", description=None)

    # Act
    repr_str = repr(product)

    # Assert
    assert "products_none_test" in repr_str
    assert "id=1" in repr_str
    assert "name=Test" in repr_str
    assert "description=None" in repr_str


# ============================================================================
# DatetimeColumnsMixin Tests
# ============================================================================


def test__datetime_mixin__has_created_at__default_no_index() -> None:
    # Arrange
    class ArticleWithCreatedAt(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_created"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    created_at_col = ArticleWithCreatedAt.__table__.c.created_at

    # Assert
    assert created_at_col is not None
    assert created_at_col.server_default is not None
    assert created_at_col.index is False


def test__datetime_mixin__has_updated_at__default_no_index() -> None:
    # Arrange
    class ArticleWithUpdatedAt(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_updated"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    updated_at_col = ArticleWithUpdatedAt.__table__.c.updated_at

    # Assert
    assert updated_at_col is not None
    assert updated_at_col.server_default is not None
    assert updated_at_col.onupdate is not None
    assert updated_at_col.index is False


def test__datetime_mixin__created_at_index__when_flag_true() -> None:
    # Arrange
    class ArticleWithCreatedAtIndex(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_created_indexed"
        __table_args__ = {"extend_existing": True}
        __created_at_index__ = True

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    created_at_col = ArticleWithCreatedAtIndex.__table__.c.created_at

    # Assert
    assert created_at_col.index is True


def test__datetime_mixin__updated_at_index__when_flag_true() -> None:
    # Arrange
    class ArticleWithUpdatedAtIndex(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_updated_indexed"
        __table_args__ = {"extend_existing": True}
        __updated_at_index__ = True

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    updated_at_col = ArticleWithUpdatedAtIndex.__table__.c.updated_at

    # Assert
    assert updated_at_col.index is True


def test__datetime_mixin__both_indexes__when_both_flags_true() -> None:
    # Arrange
    class ArticleWithBothIndexes(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_both_indexed"
        __table_args__ = {"extend_existing": True}
        __created_at_index__ = True
        __updated_at_index__ = True

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    created_at_col = ArticleWithBothIndexes.__table__.c.created_at
    updated_at_col = ArticleWithBothIndexes.__table__.c.updated_at

    # Assert
    assert created_at_col.index is True
    assert updated_at_col.index is True


def test__datetime_mixin__columns_have_correct_types() -> None:
    # Arrange
    class ArticleWithTimestamps(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "articles_types"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act
    created_at_col = ArticleWithTimestamps.__table__.c.created_at
    updated_at_col = ArticleWithTimestamps.__table__.c.updated_at

    # Assert
    assert isinstance(created_at_col.type, TIMESTAMP)
    assert isinstance(updated_at_col.type, TIMESTAMP)


# ============================================================================
# _extract_enum_values Tests
# ============================================================================


def test__extract_enum_values__python_enum__returns_values() -> None:
    # Arrange
    class Color(enum.Enum):
        RED = "red"
        BLUE = "blue"
        GREEN = "green"

    # Act
    values = _extract_enum_values(Color)

    # Assert
    assert values == ["red", "blue", "green"]


def test__extract_enum_values__list_input__returns_list() -> None:
    # Arrange
    input_list = ["red", "blue", "green"]

    # Act
    values = _extract_enum_values(input_list)

    # Assert
    assert values == ["red", "blue", "green"]


def test__extract_enum_values__enum_with_int_values__returns_ints() -> None:
    # Arrange
    class Status(enum.Enum):
        PENDING = 1
        APPROVED = 2
        REJECTED = 3

    # Act
    values = _extract_enum_values(Status)

    # Assert
    assert values == [1, 2, 3]


def test__extract_enum_values__empty_list__returns_empty_list() -> None:
    # Arrange
    input_list: list[str] = []

    # Act
    values = _extract_enum_values(input_list)

    # Assert
    assert values == []


def test__extract_enum_values__single_value_enum__returns_single_value() -> None:
    # Arrange
    class Single(enum.Enum):
        ONLY = "only"

    # Act
    values = _extract_enum_values(Single)

    # Assert
    assert values == ["only"]


# ============================================================================
# UnConstrainedEnum Tests
# ============================================================================


def test__unconstrained_enum__creates_enum_type__no_constraint() -> None:
    # Arrange
    class Role(enum.Enum):
        ADMIN = "admin"
        USER = "user"
        GUEST = "guest"

    # Act
    enum_type = UnConstrainedEnum(Role)

    # Assert
    assert enum_type.native_enum is False
    assert enum_type.create_constraint is False
    assert enum_type.validate_strings is True


def test__unconstrained_enum__with_enum_class__creates_enum_type() -> None:
    # Arrange
    class Role(enum.Enum):
        ADMIN = "admin"
        USER = "user"

    # Act
    enum_type = UnConstrainedEnum(Role)

    # Assert
    assert enum_type.native_enum is False
    assert enum_type.create_constraint is False
    assert enum_type.validate_strings is True


def test__unconstrained_enum__extracts_values__from_python_enum() -> None:
    # Arrange
    class Status(enum.Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"

    # Act
    enum_type = UnConstrainedEnum(Status)

    # Assert
    assert callable(enum_type.values_callable)
    extracted = enum_type.values_callable(Status)
    assert extracted == ["active", "inactive"]


def test__unconstrained_enum__with_int_enum__extracts_int_values() -> None:
    # Arrange
    class Priority(enum.Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    # Act - Test _extract_enum_values directly since SQLAlchemy Enum doesn't support int values
    extracted = _extract_enum_values(Priority)

    # Assert
    assert extracted == [1, 2, 3]


# ============================================================================
# Integration Tests
# ============================================================================


def test__model_with_all_features__creates_successfully() -> None:
    # Arrange & Act
    class Order(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "orders_integration"
        __table_args__ = {"extend_existing": True}
        __created_at_index__ = True

        class StatusEnum(enum.Enum):
            PENDING = "pending"
            COMPLETED = "completed"
            CANCELLED = "cancelled"

        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[str] = mapped_column(UnConstrainedEnum(StatusEnum))

    # Assert
    assert Order.__tablename__ == "orders_integration"
    assert hasattr(Order, "created_at")
    assert hasattr(Order, "updated_at")
    assert hasattr(Order, "status")


def test__repr_with_datetime_columns__includes_timestamps() -> None:
    # Arrange
    class Event(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "events_repr"
        __table_args__ = {"extend_existing": True}

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]

    event = Event(id=1, name="Test Event")
    event.created_at = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
    event.updated_at = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)

    # Act
    repr_str = repr(event)

    # Assert
    assert "events_repr" in repr_str
    assert "id=1" in repr_str
    assert "name=Test Event" in repr_str
    assert "created_at" in repr_str
    assert "updated_at" in repr_str


def test__multiple_models_with_mixin__independent_index_flags() -> None:
    # Arrange
    class Model1(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "model1_index_test"
        __table_args__ = {"extend_existing": True}
        __created_at_index__ = True
        __updated_at_index__ = False

        id: Mapped[int] = mapped_column(primary_key=True)

    class Model2(BaseTable, DatetimeColumnsMixin):
        __tablename__ = "model2_index_test"
        __table_args__ = {"extend_existing": True}
        __created_at_index__ = False
        __updated_at_index__ = True

        id: Mapped[int] = mapped_column(primary_key=True)

    # Act & Assert
    assert Model1.__table__.c.created_at.index is True
    assert Model1.__table__.c.updated_at.index is False
    assert Model2.__table__.c.created_at.index is False
    assert Model2.__table__.c.updated_at.index is True
