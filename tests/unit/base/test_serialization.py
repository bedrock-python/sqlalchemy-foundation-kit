"""Unit tests for JSON serialization utilities."""

from __future__ import annotations

import decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ============================================================================
# _default_json_encoder Tests
# ============================================================================


def test__default_json_encoder__decimal__converts_to_string() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    decimal_value = decimal.Decimal("123.45")

    # Act
    result = _default_json_encoder(decimal_value)

    # Assert
    assert result == "123.45"
    assert isinstance(result, str)


def test__default_json_encoder__large_decimal__converts_correctly() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    large_decimal = decimal.Decimal("99999999999999999999999.123456789")

    # Act
    result = _default_json_encoder(large_decimal)

    # Assert
    assert result == "99999999999999999999999.123456789"
    assert isinstance(result, str)


def test__default_json_encoder__decimal_zero__returns_zero_string() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    zero_decimal = decimal.Decimal("0")

    # Act
    result = _default_json_encoder(zero_decimal)

    # Assert
    assert result == "0"


def test__default_json_encoder__negative_decimal__preserves_sign() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    negative = decimal.Decimal("-456.78")

    # Act
    result = _default_json_encoder(negative)

    # Assert
    assert result == "-456.78"
    assert result.startswith("-")


def test__default_json_encoder__decimal_with_exponent__normalizes() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    scientific = decimal.Decimal("1.23E+5")

    # Act
    result = _default_json_encoder(scientific)

    # Assert
    assert "1" in result
    assert "23" in result
    assert isinstance(result, str)


def test__default_json_encoder__unsupported_type__raises_type_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    unsupported_obj = object()

    # Act & Assert
    with pytest.raises(TypeError, match="Object of type object is not JSON serializable"):
        _default_json_encoder(unsupported_obj)


def test__default_json_encoder__custom_class__raises_type_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    class CustomClass:
        pass

    obj = CustomClass()

    # Act & Assert
    with pytest.raises(TypeError, match="Object of type CustomClass is not JSON serializable"):
        _default_json_encoder(obj)


def test__default_json_encoder__none__raises_type_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    # Act & Assert
    with pytest.raises(TypeError, match="Object of type NoneType is not JSON serializable"):
        _default_json_encoder(None)


def test__default_json_encoder__string__raises_type_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    # Act & Assert
    with pytest.raises(TypeError, match="Object of type str is not JSON serializable"):
        _default_json_encoder("test")


def test__default_json_encoder__int__raises_type_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _default_json_encoder

    # Act & Assert
    with pytest.raises(TypeError, match="Object of type int is not JSON serializable"):
        _default_json_encoder(42)


# ============================================================================
# _json_serializer Tests
# ============================================================================


def test__json_serializer__simple_dict__returns_json_string() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {"key": "value"}

    # Act
    result = _json_serializer(data)

    # Assert
    assert result == '{"key":"value"}'
    assert isinstance(result, str)


def test__json_serializer__nested_dict__serializes_correctly() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {"user": {"id": 1, "name": "John"}, "active": True}

    # Act
    result = _json_serializer(data)

    # Assert
    assert '"user"' in result
    assert '"id":1' in result
    assert '"name":"John"' in result
    assert '"active":true' in result


def test__json_serializer__list__serializes_correctly() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = [1, 2, 3, "test"]

    # Act
    result = _json_serializer(data)

    # Assert
    assert result == '[1,2,3,"test"]'


def test__json_serializer__empty_dict__returns_empty_json() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {}

    # Act
    result = _json_serializer(data)

    # Assert
    assert result == "{}"


def test__json_serializer__empty_list__returns_empty_array() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = []

    # Act
    result = _json_serializer(data)

    # Assert
    assert result == "[]"


def test__json_serializer__with_decimal__uses_default_encoder() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {"amount": decimal.Decimal("123.45")}

    # Act
    result = _json_serializer(data)

    # Assert
    assert '"amount":"123.45"' in result


def test__json_serializer__complex_with_decimal__serializes_all() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {
        "user": {"id": 1, "balance": decimal.Decimal("100.50")},
        "items": [{"price": decimal.Decimal("25.99")}],
    }

    # Act
    result = _json_serializer(data)

    # Assert
    assert '"balance":"100.50"' in result
    assert '"price":"25.99"' in result


def test__json_serializer__orjson_not_installed__raises_import_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.serialization.require_optional") as mock_require:
        mock_require.side_effect = ImportError("orjson is required")

        with pytest.raises(ImportError, match="orjson is required"):
            _json_serializer({"key": "value"})


def test__json_serializer__orjson_dumps_fails__logs_and_raises() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    mock_orjson = MagicMock()
    mock_orjson.dumps.side_effect = ValueError("Serialization error")

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.serialization.require_optional", return_value=mock_orjson):
        with patch("sqlalchemy_foundation_kit.base.serialization.logger") as mock_logger:
            with pytest.raises(TypeError, match="Cannot serialize dict to JSON"):
                _json_serializer({"key": "value"})

            mock_logger.exception.assert_called_once_with("Failed to serialize %s to JSON", "dict")


def test__json_serializer__unsupported_object__raises_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    class CustomClass:
        pass

    data = {"obj": CustomClass()}

    # Act & Assert
    with pytest.raises(TypeError):
        _json_serializer(data)


def test__json_serializer__returns_utf8_decoded_string() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer

    data = {"text": "Hello 世界"}

    # Act
    result = _json_serializer(data)

    # Assert
    assert isinstance(result, str)
    assert "Hello" in result
    assert "世界" in result


# ============================================================================
# configure_orjson_serialization Tests
# ============================================================================


def test__configure_orjson_serialization__returns_dict() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert isinstance(result, dict)


def test__configure_orjson_serialization__contains_json_serializer() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert "json_serializer" in result
    assert callable(result["json_serializer"])


def test__configure_orjson_serialization__contains_json_deserializer() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert "json_deserializer" in result
    assert callable(result["json_deserializer"])


def test__configure_orjson_serialization__has_two_keys() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert len(result) == 2
    assert set(result.keys()) == {"json_serializer", "json_deserializer"}


def test__configure_orjson_serialization__serializer_is_internal_function() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import _json_serializer, configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert result["json_serializer"] is _json_serializer


def test__configure_orjson_serialization__deserializer_is_orjson_loads() -> None:
    # Arrange
    import orjson

    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    result = configure_orjson_serialization()

    # Assert
    assert result["json_deserializer"] is orjson.loads


def test__configure_orjson_serialization__orjson_not_installed__raises_import_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.serialization.require_optional") as mock_require:
        mock_require.side_effect = ImportError("orjson is required for this functionality")

        with pytest.raises(ImportError, match="orjson is required"):
            configure_orjson_serialization()


def test__configure_orjson_serialization__can_serialize_dict() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]
    data = {"test": "value"}

    # Act
    result = serializer(data)

    # Assert
    assert result == '{"test":"value"}'


def test__configure_orjson_serialization__can_deserialize_json() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    deserializer = config["json_deserializer"]
    json_string = b'{"test":"value"}'

    # Act
    result = deserializer(json_string)

    # Assert
    assert result == {"test": "value"}


def test__configure_orjson_serialization__round_trip_with_decimal() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]
    deserializer = config["json_deserializer"]
    data = {"amount": decimal.Decimal("123.45")}

    # Act
    serialized = serializer(data)
    deserialized = deserializer(serialized.encode("utf-8"))

    # Assert
    assert deserialized == {"amount": "123.45"}  # Decimal becomes string


def test__configure_orjson_serialization__idempotent__same_references() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    # Act
    config1 = configure_orjson_serialization()
    config2 = configure_orjson_serialization()

    # Assert
    assert config1["json_serializer"] is config2["json_serializer"]
    assert config1["json_deserializer"] is config2["json_deserializer"]


# ============================================================================
# Integration Tests
# ============================================================================


def test__full_serialization_pipeline__complex_data() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]
    deserializer = config["json_deserializer"]

    complex_data = {
        "user": {"id": 1, "name": "John", "balance": decimal.Decimal("1000.50")},
        "orders": [
            {"id": 1, "total": decimal.Decimal("25.99")},
            {"id": 2, "total": decimal.Decimal("50.00")},
        ],
        "meta": {"active": True, "count": 2},
    }

    # Act
    serialized = serializer(complex_data)
    deserialized = deserializer(serialized.encode("utf-8"))

    # Assert
    assert deserialized["user"]["name"] == "John"
    assert deserialized["user"]["balance"] == "1000.50"
    assert len(deserialized["orders"]) == 2
    assert deserialized["orders"][0]["total"] == "25.99"
    assert deserialized["meta"]["active"] is True


def test__serialization__empty_objects() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]

    # Act & Assert
    assert serializer({}) == "{}"
    assert serializer([]) == "[]"
    assert serializer({"empty": {}}) == '{"empty":{}}'
    assert serializer({"empty": []}) == '{"empty":[]}'


def test__serialization__special_characters() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]
    deserializer = config["json_deserializer"]

    data = {"text": 'Hello "World" \n\t', "unicode": "😀🎉", "special": "\\n\\t"}

    # Act
    serialized = serializer(data)
    deserialized = deserializer(serialized.encode("utf-8"))

    # Assert
    assert deserialized["text"] == 'Hello "World" \n\t'
    assert deserialized["unicode"] == "😀🎉"
    assert deserialized["special"] == "\\n\\t"


def test__serialization__numeric_types() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.serialization import configure_orjson_serialization

    config = configure_orjson_serialization()
    serializer = config["json_serializer"]

    data = {
        "int": 42,
        "float": 3.14,
        "negative": -100,
        "zero": 0,
        "decimal": decimal.Decimal("99.99"),
    }

    # Act
    result = serializer(data)

    # Assert
    assert '"int":42' in result
    assert '"float":3.14' in result
    assert '"negative":-100' in result
    assert '"zero":0' in result
    assert '"decimal":"99.99"' in result
