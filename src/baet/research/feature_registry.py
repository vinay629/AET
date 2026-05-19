"""Feature registry for BAET.

Every feature is registered with:
- name: unique identifier
- version: semantic version
- lookback: how much history is needed
- depends_on: other features this depends on
- leakage_checked: has it been verified for no future leakage
- deterministic: same input → same output
- bounded_latency: max computation time

Features must pass governance checks before use in experiments.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureSpec:
    """Specification for a single feature."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    lookback: int = 0           # Number of candles needed
    depends_on: list[str] = field(default_factory=list)
    leakage_checked: bool = False
    deterministic: bool = True
    max_latency_ms: float = 100.0
    category: str = "technical"  # technical, volume, volatility, custom
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def feature_id(self) -> str:
        return f"{self.name}_v{self.version}"

    @property
    def content_hash(self) -> str:
        content = json.dumps({
            "name": self.name,
            "version": self.version,
            "lookback": self.lookback,
            "parameters": self.parameters,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class FeatureValidationResult:
    """Result of validating a feature."""
    feature_id: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


class FeatureRegistry:
    """
    Registry for all features used in research and production.

    Enforces:
    - No future leakage (governance check)
    - Deterministic computation
    - Bounded latency
    - Dependency resolution
    """

    def __init__(self, registry_dir: Path | None = None) -> None:
        self._features: dict[str, FeatureSpec] = {}
        self._builders: dict[str, callable] = {}
        self._registry_dir = registry_dir
        if registry_dir:
            registry_dir.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        spec: FeatureSpec,
        builder: callable,
    ) -> None:
        """Register a feature with its builder function."""
        fid = spec.feature_id
        if fid in self._features:
            logger.warning(f"Overwriting feature: {fid}")

        self._features[fid] = spec
        self._builders[fid] = builder
        logger.info(f"Feature registered: {fid} (lookback={spec.lookback})")

    def get(self, name: str, version: str = "1.0.0") -> FeatureSpec | None:
        """Get a feature specification."""
        fid = f"{name}_v{version}"
        return self._features.get(fid)

    def build(
        self,
        name: str,
        data: pd.DataFrame,
        version: str = "1.0.0",
        **kwargs: Any,
    ) -> pd.Series:
        """Build a feature from data."""
        fid = f"{name}_v{version}"
        builder = self._builders.get(fid)
        if builder is None:
            raise ValueError(f"Feature not registered: {fid}")
        return builder(data, **kwargs)

    def build_all(
        self,
        data: pd.DataFrame,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        """Build all registered features (or a subset)."""
        result = data.copy()
        to_build = features or list(self._features.keys())

        # Resolve dependencies
        ordered = self._resolve_dependencies(to_build)

        for fid in ordered:
            spec = self._features[fid]
            builder = self._builders[fid]
            try:
                result[spec.name] = builder(result, **spec.parameters)
            except Exception as e:
                logger.error(f"Failed to build feature {fid}: {e}")
                result[spec.name] = 0.0

        return result

    def validate(
        self,
        name: str,
        data: pd.DataFrame,
        version: str = "1.0.0",
    ) -> FeatureValidationResult:
        """
        Validate a feature against governance checks.

        Checks:
        1. No future leakage (feature at time t only uses data ≤ t)
        2. Deterministic (same input → same output)
        3. Bounded latency
        4. No NaN in output (unless expected)
        5. Finite values only
        """
        fid = f"{name}_v{version}"
        spec = self._features.get(fid)
        builder = self._builders.get(fid)

        if spec is None or builder is None:
            return FeatureValidationResult(
                feature_id=fid,
                passed=False,
                errors=[f"Feature not registered: {fid}"],
            )

        result = FeatureValidationResult(feature_id=fid, passed=True)
        errors = []
        warnings = []
        checks = {}

        # Check 1: Latency
        start = time.monotonic()
        try:
            output = builder(data, **spec.parameters)
            latency_ms = (time.monotonic() - start) * 1000
            result.latency_ms = latency_ms
            checks["latency"] = latency_ms <= spec.max_latency_ms
            if not checks["latency"]:
                warnings.append(
                    f"Latency {latency_ms:.1f}ms exceeds max {spec.max_latency_ms}ms"
                )
        except Exception as e:
            errors.append(f"Build failed: {e}")
            result.passed = False
            result.errors = errors
            result.warnings = warnings
            result.checks = checks
            return result

        # Check 2: Deterministic
        try:
            output2 = builder(data, **spec.parameters)
            checks["deterministic"] = output.equals(output2)
            if not checks["deterministic"]:
                errors.append("Feature is not deterministic")
        except Exception:
            checks["deterministic"] = False
            warnings.append("Could not verify determinism")

        # Check 3: No NaN
        nan_count = output.isna().sum()
        checks["no_nan"] = nan_count == 0
        if not checks["no_nan"]:
            warnings.append(f"Output contains {nan_count} NaN values")

        # Check 4: Finite values
        try:
            output_arr = np.asarray(output, dtype=float)
            inf_count = int((~np.isfinite(output_arr) & ~np.isnan(output_arr)).sum())
            checks["finite"] = inf_count == 0
            if not checks["finite"]:
                errors.append(f"Output contains {inf_count} infinite values")
        except (ValueError, TypeError):
            checks["finite"] = True  # Non-numeric output, skip

        # Check 5: Leakage (basic check — correlation with future returns)
        if "close" in data.columns and len(data) > 10:
            future_return = data["close"].pct_change().shift(-1)
            valid = pd.concat([output, future_return], axis=1).dropna()
            if len(valid) > 5:
                corr = valid.iloc[:, 0].corr(valid.iloc[:, 1])
                # High correlation with future returns suggests leakage
                checks["no_leakage"] = abs(corr) < 0.95
                if not checks["no_leakage"]:
                    warnings.append(
                        f"High correlation with future returns ({corr:.3f}) — "
                        f"possible leakage"
                    )

        result.passed = all(checks.values()) and len(errors) == 0
        result.checks = checks
        result.errors = errors
        result.warnings = warnings

        if result.passed:
            logger.info(f"Feature {fid} passed all validation checks")
        else:
            logger.warning(
                f"Feature {fid} failed validation: "
                f"{', '.join(errors + warnings)}"
            )

        return result

    def validate_all(
        self,
        data: pd.DataFrame,
    ) -> list[FeatureValidationResult]:
        """Validate all registered features."""
        results = []
        for fid in self._features:
            name = self._features[fid].name
            version = self._features[fid].version
            results.append(self.validate(name, data, version))
        return results

    def list_features(
        self,
        category: str | None = None,
        leakage_checked: bool | None = None,
    ) -> list[FeatureSpec]:
        """List registered features, optionally filtered."""
        specs = list(self._features.values())
        if category:
            specs = [s for s in specs if s.category == category]
        if leakage_checked is not None:
            specs = [s for s in specs if s.leakage_checked == leakage_checked]
        return specs

    def _resolve_dependencies(self, feature_ids: list[str]) -> list[str]:
        """Topological sort of features by dependency."""
        visited = set()
        result = []

        def visit(fid: str) -> None:
            if fid in visited:
                return
            visited.add(fid)
            spec = self._features.get(fid)
            if spec:
                for dep_name in spec.depends_on:
                    # Find the feature ID for this dependency
                    for dep_fid, dep_spec in self._features.items():
                        if dep_spec.name == dep_name:
                            visit(dep_fid)
                            break
                result.append(fid)

        for fid in feature_ids:
            visit(fid)

        return result

    def save(self) -> None:
        """Save registry to disk."""
        if not self._registry_dir:
            return
        registry_file = self._registry_dir / "feature_registry.json"
        data = {
            fid: {
                "name": spec.name,
                "version": spec.version,
                "description": spec.description,
                "lookback": spec.lookback,
                "depends_on": spec.depends_on,
                "leakage_checked": spec.leakage_checked,
                "deterministic": spec.deterministic,
                "max_latency_ms": spec.max_latency_ms,
                "category": spec.category,
                "parameters": spec.parameters,
                "content_hash": spec.content_hash,
            }
            for fid, spec in self._features.items()
        }
        with registry_file.open("w") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self) -> None:
        """Load registry from disk."""
        if not self._registry_dir:
            return
        registry_file = self._registry_dir / "feature_registry.json"
        if not registry_file.exists():
            return
        with registry_file.open("r") as f:
            data = json.load(f)
        for fid, spec_data in data.items():
            self._features[fid] = FeatureSpec(**{
                k: v for k, v in spec_data.items()
                if k != "content_hash"
            })
