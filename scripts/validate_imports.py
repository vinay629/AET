"""
Architectural boundary enforcement via import validation.

Validates that no module imports from a higher layer, preventing
circular dependencies and layering violations.

Run:
    python scripts/validate_imports.py

Exit code 0 = all boundaries respected.
Exit code 1 = violations found.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Layer definitions: module path → layer number (higher = more outer)
# Outer layers may import from inner layers, never the reverse.
LAYERS: list[tuple[str, int]] = [
    ("src/baet/config", 0),
    ("src/baet/data", 0),
    ("src/baet/ml", 1),
    ("src/baet/core", 2),
    ("src/baet/risk", 3),
    ("src/baet/execution", 4),
    ("src/baet/strategies", 5),
    ("src/baet/research", 5),
    ("src/baet/regimes", 5),
    ("src/baet/reporting", 5),
    ("src/baet/paper", 5),
    ("src/baet/live", 5),
    ("src/baet/plugins", 5),
    ("src/baet/dashboard", 6),
    ("src/baet/cli", 6),
]

# Exceptions: specific cross-layer imports that are allowed.
# Each exception must be documented with a reason.
# Format: (source_prefix, target_prefix) where "*" matches any source.
ALLOWED_CROSSINGS: list[tuple[str, str]] = [
    # Config is read-only at runtime, safe for all layers to import
    ("*", "src/baet/config"),
    # Data layer is read-only, safe for all layers to import
    ("*", "src/baet/data"),
    # Core events are the universal language — all layers emit/consume
    ("*", "src/baet/core/events"),
    # Core enums are shared constants
    ("*", "src/baet/core/enums"),
    # Structured logging is a cross-cutting concern
    ("*", "src/baet/core/structured_log"),
    # Health checks are cross-cutting
    ("*", "src/baet/core/health"),
    # Clock is a shared utility
    ("*", "src/baet/core/clock"),
    # Invariants are shared validation
    ("*", "src/baet/core/invariants"),
    # Models (data classes) are shared contracts
    ("*", "src/baet/core/models"),
    # Config models reference RiskPolicy for config-driven risk policy selection.
    # This is a read-time config mapping, not a runtime dependency.
    ("src/baet/config", "src/baet/risk"),
    # Data pipeline is the composition root — it orchestrates across layers
    # (strategies, execution, reporting) to wire the research workflow.
    # Uses lazy imports to avoid hard circular dependencies.
    ("src/baet/data", "src/baet/strategies"),
    ("src/baet/data", "src/baet/reporting"),
    ("src/baet/data", "src/baet/execution"),
    # Execution backtest imports strategy adapters for signal normalization.
    # This is a one-way adaptation from strategy output to execution input.
    ("src/baet/execution", "src/baet/strategies/adapters"),
]


def get_layer(module_path: str) -> int | None:
    """Get the layer number for a module path. Returns None if not in any layer."""
    for prefix, layer in LAYERS:
        if module_path.startswith(prefix):
            return layer
    return None


def is_baet_module(import_path: str) -> bool:
    """Check if an import path is a BAET internal module."""
    return import_path.startswith("baet.")


def resolve_relative_import(source_file: str, import_path: str) -> str | None:
    """Resolve a relative import to an absolute module path."""
    if not import_path.startswith("baet."):
        return None
    # Convert baet.X.Y to src/baet/X/Y
    parts = import_path.split(".")
    if len(parts) < 2:
        return None
    return "src/" + "/".join(parts)


def check_file(file_path: Path) -> list[str]:
    """Check a single Python file for import violations. Returns list of violations."""
    violations: list[str] = []

    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return violations  # Skip files with syntax errors (other tools catch those)

    # Determine the layer of the source file
    source_module = "src/" + str(file_path.relative_to(Path("src"))).replace("\\", "/")
    if source_module.endswith(".py"):
        source_module = source_module[:-3]
    if source_module.endswith("/__init__"):
        source_module = source_module[: -len("/__init__")]

    source_layer = get_layer(source_module)
    if source_layer is None:
        return violations  # File not in a tracked layer

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(source_module, source_layer, alias.name, str(file_path), violations)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            # Handle relative imports by resolving the module
            module = node.module
            if node.level > 0:
                # Relative import — resolve against the source file's package
                parts = source_module.split("/")
                # Go up `level` directories
                if node.level <= len(parts):
                    base = "/".join(parts[: -node.level]) if node.level < len(parts) else ""
                    if module:
                        module = f"{base}/{module}" if base else module
                    else:
                        module = base
                    # Convert file path to module path
                    module = module.replace("src/", "").replace("/", ".")
                else:
                    continue  # Can't resolve, skip
            _check_import(source_module, source_layer, module, str(file_path), violations)

    return violations


def _check_import(
    source_module: str,
    source_layer: int,
    imported_module: str,
    file_path: str,
    violations: list[str],
) -> None:
    """Check if a single import violates layer boundaries."""
    if not is_baet_module(imported_module):
        return  # External import, not our concern

    # Resolve to path
    imported_path = "src/" + imported_module.replace(".", "/")

    # Check allowed crossings first
    for allowed_source, allowed_target in ALLOWED_CROSSINGS:
        if allowed_source == "*" or source_module.startswith(allowed_source):
            if imported_path.startswith(allowed_target):
                return  # Explicitly allowed

    # Determine the layer of the imported module
    imported_layer = get_layer(imported_path)
    if imported_layer is None:
        return  # Not in a tracked layer

    # Check: source layer must be >= imported layer (outer can import inner)
    if source_layer < imported_layer:
        violations.append(
            f"{file_path}: layer {source_layer} ({source_module}) "
            f"imports from layer {imported_layer} ({imported_module})"
        )


def main() -> int:
    """Main entry point. Returns exit code."""
    src_dir = Path("src/baet")
    if not src_dir.exists():
        print("ERROR: src/baet directory not found", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    py_files = sorted(src_dir.rglob("*.py"))

    for py_file in py_files:
        violations = check_file(py_file)
        all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} architectural boundary violation(s):\n")
        for v in all_violations:
            print(f"  [FAIL] {v}")
        print("\nOuter layers must not import from inner layers.")
        print("See .github/instructions/architecture-boundaries.instructions.md for the layer map.")
        return 1

    print(f"[OK] All import boundaries respected ({len(py_files)} files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
