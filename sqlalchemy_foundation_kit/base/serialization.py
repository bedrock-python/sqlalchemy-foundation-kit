"""JSON serialization utilities for SQLAlchemy."""

from __future__ import annotations

import decimal
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _ensure_orjson_available() -> Any:
    """Ensure orjson is installed and return the module.

    Returns:
        The orjson module.

    Raises:
        ImportError: If orjson is not installed.

    Examples:
        >>> orjson = _ensure_orjson_available()
        >>> hasattr(orjson, 'dumps')
        True
    """
    try:
        import orjson  # noqa: PLC0415
    except ImportError as e:
        raise ImportError(
            "orjson is required for JSON serialization. Install with: pip install sqlalchemy-foundation-kit[orjson]"
        ) from e
    else:
        return orjson


def _default_json_encoder(obj: object) -> str:
    """JSON encoder for types not supported by orjson.

    Handles special types like decimal.Decimal that orjson doesn't support natively.

    Args:
        obj: The object to encode.

    Returns:
        String representation of the object.

    Raises:
        TypeError: If the object type is not supported.

    Examples:
        >>> from decimal import Decimal
        >>> _default_json_encoder(Decimal("123.45"))
        '123.45'
        >>> _default_json_encoder(object())
        Traceback (most recent call last):
        ...
        TypeError
    """
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _json_serializer(obj: object) -> str:
    """High-performance JSON serializer using orjson.

    Provides fast JSON serialization with fallback handling for types
    like decimal.Decimal via the default encoder.

    Args:
        obj: The object to serialize.

    Returns:
        UTF-8 encoded JSON string.

    Raises:
        ImportError: If orjson is not installed.

    Examples:
        >>> _json_serializer({"key": "value"})
        '{"key":"value"}'
    """
    orjson = _ensure_orjson_available()

    try:
        return orjson.dumps(obj, default=_default_json_encoder).decode("utf-8")  # type: ignore[no-any-return]
    except Exception:
        logger.exception("Failed to serialize object to JSON")
        raise


def configure_orjson_serialization() -> dict[str, object]:
    """Configure orjson serialization for SQLAlchemy engine.

    Returns:
        Dictionary with json_serializer and json_deserializer configured.

    Raises:
        ImportError: If orjson is not installed.

    Examples:
        >>> config = configure_orjson_serialization()
        >>> "json_serializer" in config
        True
        >>> "json_deserializer" in config
        True
    """
    orjson = _ensure_orjson_available()

    return {
        "json_serializer": _json_serializer,
        "json_deserializer": orjson.loads,
    }


__all__ = [
    "configure_orjson_serialization",
]

# Note: _default_json_encoder and _json_serializer are private internal helpers
# used by configure_orjson_serialization(). They are not part of the public API.
