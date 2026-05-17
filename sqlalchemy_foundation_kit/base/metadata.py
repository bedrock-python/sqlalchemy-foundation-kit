"""ORM metadata loading utilities."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module

from sqlalchemy import MetaData

from .models import Base


def load_orm_metadata(models_modules: Iterable[str], metadata: MetaData | None = None) -> MetaData:
    """Load all ORM models metadata synchronously.

    Imports specified modules to ensure that all SQLAlchemy models are
    registered in the metadata. This is useful for migrations and schema
    introspection with tools like Alembic.

    Args:
        models_modules: Iterable of module paths to import (e.g., ["myapp.models", "myapp.core.models"]).
        metadata: Optional specific MetaData object to use. If None, uses Base.metadata.

    Returns:
        MetaData object containing all registered models from the imported modules.

    Examples:
        Load models from multiple modules:
            >>> from sqlalchemy_foundation_kit.base import load_orm_metadata
            >>> metadata = load_orm_metadata([
            ...     "myapp.users.models",
            ...     "myapp.orders.models",
            ...     "myapp.products.models",
            ... ])
            >>> len(metadata.tables)
            15

        Use with custom metadata:
            >>> from sqlalchemy import MetaData
            >>> custom_meta = MetaData(schema="public")
            >>> metadata = load_orm_metadata(["myapp.models"], metadata=custom_meta)

        Typical usage in Alembic env.py:
            >>> from sqlalchemy_foundation_kit.base import Base, load_orm_metadata
            >>> target_metadata = Base.metadata
            >>> load_orm_metadata(["myapp.models"])  # Register all models
            >>> # Now target_metadata.tables contains all tables
    """
    for module in models_modules:
        import_module(module)

    return metadata if metadata is not None else Base.metadata


__all__ = [
    "load_orm_metadata",
]
