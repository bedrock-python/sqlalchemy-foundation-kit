"""Unit tests for importing contrib packages without their extra installed.

The check has to happen in a subprocess: the failure is at *import* time, in a class
body, so it cannot be reproduced by patching a flag inside an already-imported module.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

_IMPORT_WITH_DEPENDENCY_HIDDEN = """
import sys
from importlib.abc import MetaPathFinder


class Blocker(MetaPathFinder):
    def __init__(self, name):
        self._name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self._name or fullname.startswith(self._name + "."):
            raise ImportError(f"No module named {{fullname!r}}")
        return None


sys.meta_path.insert(0, Blocker({dependency!r}))

try:
    import {module}
except ImportError as exc:
    print(type(exc).__name__, exc)
else:
    print("imported without error")
"""


def _import_with_dependency_hidden(module: str, dependency: str) -> str:
    script = _IMPORT_WITH_DEPENDENCY_HIDDEN.format(module=module, dependency=dependency)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.mark.unit
def test__import_contrib_di__without_dishka__raises_import_error_naming_the_extra() -> None:
    # Arrange & Act
    output = _import_with_dependency_hidden("sqlalchemy_foundation_kit.contrib.di", "dishka")

    # Assert
    assert output.startswith("ImportError")
    assert "sqlalchemy-foundation-kit[dishka]" in output


@pytest.mark.unit
def test__import_contrib_dependency_injector__without_it__raises_import_error_naming_the_extra() -> None:
    # Arrange & Act
    output = _import_with_dependency_hidden(
        "sqlalchemy_foundation_kit.contrib.dependency_injector",
        "dependency_injector",
    )

    # Assert
    assert output.startswith("ImportError")
    assert "sqlalchemy-foundation-kit[dependency-injector]" in output
