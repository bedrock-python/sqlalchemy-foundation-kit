"""Custom SQLAlchemy types."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

T = TypeVar("T")
logger = logging.getLogger(__name__)


# Convenience alias for raw JSON dict columns.
# Use this when you don't need Pydantic validation — e.g. ``Mapped[GenericJSONDict]``.
GenericJSONDict = dict[str, Any]


class PydanticJSONB(TypeDecorator):
    """SQLAlchemy TypeDecorator for Pydantic models stored as JSONB.

    Validates and serializes values against the supplied Pydantic-compatible type
    on both write and read paths. A ``model_type`` is **required** — if you need
    raw dict storage without validation, use SQLAlchemy's built-in ``JSONB`` directly
    (or the :data:`GenericJSONDict` alias).
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model_type: type[T], *args: Any, **kwargs: Any) -> None:
        """Initialize the type decorator.

        Args:
            model_type: Pydantic model class (or any type compatible with
                ``pydantic.TypeAdapter``) used to validate and serialize values.
        """
        self.model_type = model_type
        self.adapter: TypeAdapter[T] = TypeAdapter(model_type)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        # Validate before dump to avoid Pydantic serialization warnings when value
        # is a dict (e.g. from model_dump()). This ensures value matches the expected
        # schema and converts it to a model instance if needed.
        validated = self.adapter.validate_python(value)
        return self.adapter.dump_python(validated, mode="json")

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        try:
            return self.adapter.validate_python(value)
        except ValidationError:
            logger.warning(
                "Validation error while loading %s from JSONB. Using raw data. "
                "This may indicate legacy data that doesn't match current schema.",
                self.model_type,
            )
            return value


__all__ = [
    "GenericJSONDict",
    "PydanticJSONB",
]
