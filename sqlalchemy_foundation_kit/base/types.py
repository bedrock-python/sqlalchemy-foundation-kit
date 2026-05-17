"""Custom SQLAlchemy types."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

T = TypeVar("T")
logger = logging.getLogger(__name__)


class GenericJSONDict(BaseModel):
    """Generic Pydantic model for JSON fields without a specific schema."""

    model_config = {"extra": "ignore"}


class PydanticJSONB(TypeDecorator):
    """SQLAlchemy TypeDecorator for Pydantic models stored as JSONB.

    Ensures that data is always a Pydantic model when read from the database,
    and serialized correctly when saved.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model_type: type[T] | None = None, *args: Any, **kwargs: Any) -> None:
        actual_model_type = model_type or GenericJSONDict
        self.model_type = actual_model_type
        self.adapter = TypeAdapter(actual_model_type)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        try:
            # Use validate_python before dump_python to avoid Pydantic serialization warnings
            # when value is a dict (e.g. from model_dump()). This ensures value matches
            # the expected schema and converts it to a model instance if needed.
            validated = self.adapter.validate_python(value)
            return self.adapter.dump_python(validated, mode="json")
        except Exception as e:
            logger.warning("Error while dumping %s to JSONB: %s", self.model_type, e)
            return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        try:
            return self.adapter.validate_python(value)
        except ValidationError as e:
            logger.warning(
                "Validation error while loading %s from JSONB: %s. Using raw data.",
                self.model_type,
                e,
            )
            return value
