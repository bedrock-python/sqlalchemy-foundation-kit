"""Database base models and mixins."""

from __future__ import annotations

import datetime
import uuid
from functools import partial
from typing import Any, ClassVar

from sqlalchemy import TIMESTAMP, Enum, MetaData, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import TypeEngine

DB_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map: ClassVar[dict[type, TypeEngine[Any]]] = {
        uuid.UUID: postgresql.UUID(),
        datetime.datetime: TIMESTAMP(timezone=True),
    }
    metadata = MetaData(naming_convention=DB_NAMING_CONVENTION)


class BaseTable(Base):
    """Base table class with __repr__."""

    __abstract__ = True

    def __repr__(self) -> str:
        columns = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        return f"<{self.__tablename__}: {', '.join(f'{k}={v}' for k, v in columns.items())}>"


class DatetimeColumnsMixin:
    """Mixin for tables that need created_at and updated_at timestamps.

    Control indexing via __created_at_index__ and __updated_at_index__ class variables in the model.
    Defaults to False.
    """

    __created_at_index__: ClassVar[bool] = False
    __updated_at_index__: ClassVar[bool] = False

    @declared_attr
    def created_at(self) -> Mapped[datetime.datetime]:
        return mapped_column(
            server_default=func.timezone("UTC", func.now()),
            index=self.__created_at_index__,
        )

    @declared_attr
    def updated_at(self) -> Mapped[datetime.datetime]:
        return mapped_column(
            server_default=func.timezone("UTC", func.now()),
            onupdate=func.timezone("UTC", func.now()),
            index=self.__updated_at_index__,
        )


UnConstrainedEnum = partial(
    Enum,
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
    values_callable=lambda obj: [getattr(item, "value", item) for item in obj] if hasattr(obj, "__members__") else obj,
)
