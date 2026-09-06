"""Unit tests for what the distribution promises to install."""

from __future__ import annotations

from importlib.metadata import requires

import pytest

DISTRIBUTION = "sqlalchemy-foundation-kit"


def _unconditional_requirements() -> list[str]:
    """Requirements installed by ``pip install sqlalchemy-foundation-kit``, extras aside."""
    return [requirement for requirement in requires(DISTRIBUTION) or [] if "extra ==" not in requirement]


@pytest.mark.unit
@pytest.mark.parametrize("distribution", ["sqlalchemy", "pydantic", "asyncpg"])
def test__unconditional_requirements__contains_every_import_the_package_needs(distribution: str) -> None:
    # Arrange: importing the package pulls in asyncpg (AsyncCConnection subclasses
    # asyncpg.Connection at module scope), so a plain install has to bring it.
    requirements = _unconditional_requirements()

    # Act & Assert
    assert any(requirement.startswith(distribution) for requirement in requirements), requirements
