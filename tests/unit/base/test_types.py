"""Unit tests for custom SQLAlchemy types."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy_foundation_kit.base.types import GenericJSONDict, PydanticJSONB


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""

    id: int
    name: str
    active: bool = True


# ============================================================================
# GenericJSONDict Tests
# ============================================================================


def test__generic_json_dict__is_dict_alias() -> None:
    # Arrange & Act
    value: GenericJSONDict = {"key": "value", "number": 42}

    # Assert
    assert isinstance(value, dict)
    assert value["key"] == "value"
    assert value["number"] == 42


def test__generic_json_dict__accepts_any_dict() -> None:
    # Arrange & Act
    nested: GenericJSONDict = {
        "user": {"id": 1, "name": "John"},
        "meta": {"tags": ["tag1", "tag2"]},
    }

    # Assert
    assert isinstance(nested, dict)
    assert nested["user"]["id"] == 1


def test__generic_json_dict__empty_dict__works() -> None:
    # Arrange & Act
    empty: GenericJSONDict = {}

    # Assert
    assert isinstance(empty, dict)
    assert len(empty) == 0


# ============================================================================
# PydanticJSONB Initialization Tests
# ============================================================================


def test__pydantic_jsonb__init__stores_model_type() -> None:
    # Arrange & Act
    jsonb_type = PydanticJSONB(SampleModel)

    # Assert
    assert jsonb_type.model_type == SampleModel


def test__pydantic_jsonb__init__creates_adapter() -> None:
    # Arrange & Act
    jsonb_type = PydanticJSONB(SampleModel)

    # Assert
    assert jsonb_type.adapter is not None


def test__pydantic_jsonb__impl__is_jsonb_instance() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)

    # Act & Assert
    assert isinstance(jsonb_type.impl, JSONB)
    assert type(jsonb_type.impl) == JSONB


def test__pydantic_jsonb__cache_ok__is_true() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)

    # Act & Assert
    assert jsonb_type.cache_ok is True


# ============================================================================
# process_bind_param Tests (Write to DB)
# ============================================================================


def test__process_bind_param__none_value__returns_none() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)

    # Act
    result = jsonb_type.process_bind_param(None, None)

    # Assert
    assert result is None


def test__process_bind_param__valid_model_instance__returns_dict() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    model = SampleModel(id=1, name="Test")

    # Act
    result = jsonb_type.process_bind_param(model, None)

    # Assert
    assert isinstance(result, dict)
    assert result["id"] == 1
    assert result["name"] == "Test"
    assert result["active"] is True


def test__process_bind_param__valid_dict__validates_and_returns() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    data = {"id": 2, "name": "Another"}

    # Act
    result = jsonb_type.process_bind_param(data, None)

    # Assert
    assert isinstance(result, dict)
    assert result["id"] == 2
    assert result["name"] == "Another"
    assert result["active"] is True


def test__process_bind_param__invalid_dict__raises_validation_error() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    invalid_data = {"id": "not_an_int", "name": "Test"}

    # Act & Assert
    with pytest.raises(ValidationError):
        jsonb_type.process_bind_param(invalid_data, None)


def test__process_bind_param__missing_required_field__raises_error() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    incomplete_data = {"id": 1}

    # Act & Assert
    with pytest.raises(ValidationError):
        jsonb_type.process_bind_param(incomplete_data, None)


def test__process_bind_param__extra_fields__ignored() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    data_with_extra = {"id": 1, "name": "Test", "extra": "ignored"}

    # Act
    result = jsonb_type.process_bind_param(data_with_extra, None)

    # Assert
    assert "extra" not in result
    assert result["id"] == 1


# ============================================================================
# process_result_value Tests (Read from DB)
# ============================================================================


def test__process_result_value__none_value__returns_none() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)

    # Act
    result = jsonb_type.process_result_value(None, None)

    # Assert
    assert result is None


def test__process_result_value__valid_dict__returns_model() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    data = {"id": 1, "name": "Test", "active": False}

    # Act
    result = jsonb_type.process_result_value(data, None)

    # Assert
    assert isinstance(result, SampleModel)
    assert result.id == 1
    assert result.name == "Test"
    assert result.active is False


def test__process_result_value__invalid_dict__logs_warning_returns_raw() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    invalid_data = {"id": "invalid", "name": "Test"}

    # Act
    with patch("sqlalchemy_foundation_kit.base.types.logger") as mock_logger:
        result = jsonb_type.process_result_value(invalid_data, None)

        # Assert
        assert result == invalid_data
        mock_logger.warning.assert_called_once()


def test__process_result_value__legacy_data__returns_raw_with_warning() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    legacy_data = {"old_field": "value"}

    # Act
    with patch("sqlalchemy_foundation_kit.base.types.logger") as mock_logger:
        result = jsonb_type.process_result_value(legacy_data, None)

        # Assert
        assert result == legacy_data
        mock_logger.warning.assert_called_once()


def test__process_result_value__empty_dict__returns_raw_with_warning() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    empty_data = {}

    # Act
    with patch("sqlalchemy_foundation_kit.base.types.logger") as mock_logger:
        result = jsonb_type.process_result_value(empty_data, None)

        # Assert
        assert result == empty_data
        mock_logger.warning.assert_called_once()


# ============================================================================
# Roundtrip Tests
# ============================================================================


def test__roundtrip__bind_and_result__preserves_data() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    original = SampleModel(id=42, name="Roundtrip", active=True)

    # Act
    bound = jsonb_type.process_bind_param(original, None)
    restored = jsonb_type.process_result_value(bound, None)

    # Assert
    assert isinstance(restored, SampleModel)
    assert restored.id == original.id
    assert restored.name == original.name
    assert restored.active == original.active


def test__roundtrip__with_defaults__preserves_values() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)
    original = SampleModel(id=1, name="Test")  # active defaults to True

    # Act
    bound = jsonb_type.process_bind_param(original, None)
    restored = jsonb_type.process_result_value(bound, None)

    # Assert
    assert restored.active is True


# ============================================================================
# Nested Models Tests
# ============================================================================


class Address(BaseModel):
    street: str
    city: str
    zip_code: str


class UserWithAddress(BaseModel):
    id: int
    name: str
    address: Address


def test__nested_model__bind__serializes_correctly() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(UserWithAddress)
    user = UserWithAddress(
        id=1,
        name="John",
        address=Address(street="123 Main St", city="NYC", zip_code="10001"),
    )

    # Act
    result = jsonb_type.process_bind_param(user, None)

    # Assert
    assert isinstance(result, dict)
    assert result["id"] == 1
    assert isinstance(result["address"], dict)
    assert result["address"]["street"] == "123 Main St"


def test__nested_model__result__deserializes_correctly() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(UserWithAddress)
    data = {
        "id": 1,
        "name": "John",
        "address": {"street": "123 Main St", "city": "NYC", "zip_code": "10001"},
    }

    # Act
    result = jsonb_type.process_result_value(data, None)

    # Assert
    assert isinstance(result, UserWithAddress)
    assert isinstance(result.address, Address)
    assert result.address.city == "NYC"


# ============================================================================
# Optional Fields Tests
# ============================================================================


class OptionalModel(BaseModel):
    id: int
    name: str
    description: str | None = None
    tags: list[str] | None = None


def test__optional_fields__none_values__handled_correctly() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(OptionalModel)
    model = OptionalModel(id=1, name="Test")

    # Act
    result = jsonb_type.process_bind_param(model, None)

    # Assert
    assert result["description"] is None
    assert result["tags"] is None


def test__optional_fields__provided_values__handled_correctly() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(OptionalModel)
    model = OptionalModel(id=1, name="Test", description="Desc", tags=["a", "b"])

    # Act
    result = jsonb_type.process_bind_param(model, None)

    # Assert
    assert result["description"] == "Desc"
    assert result["tags"] == ["a", "b"]


# ============================================================================
# Edge Cases Tests
# ============================================================================


def test__multiple_instances__independent_adapters() -> None:
    # Arrange & Act
    jsonb1 = PydanticJSONB(SampleModel)
    jsonb2 = PydanticJSONB(SampleModel)

    # Assert
    assert jsonb1.adapter is not jsonb2.adapter
    assert jsonb1.model_type == jsonb2.model_type


def test__scalar_returns_none__converts_to_false() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(SampleModel)

    # Act
    result = jsonb_type.process_result_value(None, None)

    # Assert
    assert result is None


def test__bind_param__all_default_values__includes_defaults() -> None:
    # Arrange
    jsonb_type = PydanticJSONB(OptionalModel)
    model = OptionalModel(id=1, name="Test")

    # Act
    result = jsonb_type.process_bind_param(model, None)

    # Assert
    assert "description" in result
    assert "tags" in result
    assert result["description"] is None
