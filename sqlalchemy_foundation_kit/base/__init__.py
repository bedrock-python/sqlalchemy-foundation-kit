"""Base ORM models and utilities.

Public API for base functionality. Import directly from submodules for clarity:
    - base.engine - Engine configuration (build_engine_kwargs, resolve_pool_class)
    - base.serialization - JSON serialization (configure_orjson_serialization)
    - base.metadata - Metadata loading (load_orm_metadata)
    - base.models - ORM base classes (Base, BaseTable, mixins)
    - base.types - Custom SQLAlchemy types (PydanticJSONB)
"""

from __future__ import annotations

from .engine import PoolClassStr, build_engine_kwargs, register_pool_class, resolve_pool_class
from .metadata import load_orm_metadata
from .models import (
    DB_NAMING_CONVENTION,
    Base,
    BaseTable,
    DatetimeColumnsMixin,
    UnConstrainedEnum,
)
from .serialization import configure_orjson_serialization
from .types import GenericJSONDict, PydanticJSONB

__all__ = [
    "DB_NAMING_CONVENTION",
    "Base",
    "BaseTable",
    "DatetimeColumnsMixin",
    "GenericJSONDict",
    "PoolClassStr",
    "PydanticJSONB",
    "UnConstrainedEnum",
    "build_engine_kwargs",
    "configure_orjson_serialization",
    "load_orm_metadata",
    "register_pool_class",
    "resolve_pool_class",
]
