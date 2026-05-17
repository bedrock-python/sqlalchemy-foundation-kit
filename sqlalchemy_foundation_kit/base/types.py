"""Custom SQLAlchemy types."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

T = TypeVar("T")
logger = logging.getLogger(__name__)


class PydanticJSONB(TypeDecorator):
    """SQLAlchemy TypeDecorator for Pydantic models stored as JSONB.

    Ensures that data is validated and serialized correctly when saved/loaded.

    When model_type is None, performs pass-through dict serialization without validation.
    When model_type is provided, validates data against the Pydantic model schema.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model_type: type[T] | None = None, *args: Any, **kwargs: Any) -> None:
        self.model_type = model_type
        self.adapter = TypeAdapter(model_type) if model_type else None
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        # Pass-through mode when no model_type specified
        if self.adapter is None:
            return value

        # Use validate_python before dump_python to avoid Pydantic serialization warnings
        # when value is a dict (e.g. from model_dump()). This ensures value matches
        # the expected schema and converts it to a model instance if needed.
        validated = self.adapter.validate_python(value)
        return self.adapter.dump_python(validated, mode="json")

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        # Pass-through mode when no model_type specified
        if self.adapter is None:
            return value

        try:
            return self.adapter.validate_python(value)
        except ValidationError:
            logger.warning(
                "Validation error while loading %s from JSONB. Using raw data. "
                "This may indicate legacy data that doesn't match current schema.",
                self.model_type,
            )
            return value
