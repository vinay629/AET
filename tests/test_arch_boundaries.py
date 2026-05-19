"""Architectural boundary tests.

Validates that the codebase respects layer boundaries:
- No upward imports (outer layers importing from inner layers)
- No circular dependencies between layers
- Shared utilities (config, events, enums) are the only cross-layer imports

These tests are deterministic and run in CI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_import_boundaries() -> None:
    """Run the import boundary validator and assert no violations."""
    result = subprocess.run(
        [sys.executable, "scripts/validate_imports.py"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0, (
        f"Architectural boundary violations found (exit code {result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_no_circular_imports() -> None:
    """Verify that importing the top-level baet package does not raise.

    A full import test catches circular dependencies that static analysis might miss.
    """
    import baet  # noqa: F401


def test_core_independence() -> None:
    """Verify that baet.core can be imported without any outer layers.

    Core is the foundation — it must not depend on risk, execution, strategies, etc.
    """
    # This is validated by the import boundary test above, but we add an explicit
    # import test to catch runtime circular imports.
    from baet.core import events, models, orders, state  # noqa: F401


def test_ml_independence() -> None:
    """Verify that baet.ml can be imported without execution or strategies.

    ML is a foundation layer — it must not depend on higher layers.
    """
    from baet.ml import leakage, purged_cv  # noqa: F401
