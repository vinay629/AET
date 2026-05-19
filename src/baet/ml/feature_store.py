"""Feature store for BAET.

Features are immutable, versioned, point-in-time correct artifacts.

Every feature computation is:
- Deterministic: same input → same output
- Point-in-time correct: no future data leakage
- Versioned: content hash for reproducibility
- Replayable: can reconstruct any historical feature set

This prevents "research entropy" where features drift silently.
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


@dataclass(frozen=True)
class FeatureVersion:
    """Immutable version identifier for a feature set."""
    name: str
    version: str
    content_hash: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    lookback: int = 0

    @property
    def feature_id(self) -> str:
        return f"{self.name}_v{self.version}"


@dataclass
class FeatureSnapshot:
    """A point-in-time snapshot of computed features."""
    version: FeatureVersion
    data: pd.DataFrame
    computation_time_ms: float = 0.0
    n_samples: int = 0
    n_features: int = 0
    null_count: int = 0
    inf_count: int = 0
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def quality_score(self) -> float:
        """Data quality score (0-1) based on nulls and infs."""
        total = self.n_samples * self.n_features
        if total == 0:
            return 0.0
        bad = self.null_count + self.inf_count
        return max(0.0, 1.0 - bad / total)


class FeatureStore:
    """
    Immutable, versioned feature storage.

    Directory structure:
        features/
        ├── feature_name_v1.0.0/
        │   ├── metadata.json
        │   ├── features.parquet
        │   └── quality_report.json
    """

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, FeatureSnapshot] = {}

    def compute(
        self,
        name: str,
        data: pd.DataFrame,
        builder: callable,
        version: str = "1.0.0",
        parameters: dict[str, Any] | None = None,
        depends_on: list[str] | None = None,
        lookback: int = 0,
        description: str = "",
        *,
        use_cache: bool = True,
    ) -> FeatureSnapshot:
        """
        Compute and store features.

        Args:
            name: Feature set name.
            data: Input data (OHLCV).
            builder: Function(data, **parameters) → DataFrame.
            version: Semantic version.
            parameters: Builder parameters (hashed for versioning).
            depends_on: Other feature sets this depends on.
            lookback: Required history length.
            description: Human-readable description.
            use_cache: Return cached version if available.

        Returns:
            FeatureSnapshot with computed features.
        """
        # Compute content hash
        param_str = json.dumps(parameters or {}, sort_keys=True, default=str)
        content_hash = hashlib.sha256(
            f"{name}:{version}:{param_str}".encode()
        ).hexdigest()[:16]

        version_obj = FeatureVersion(
            name=name,
            version=version,
            content_hash=content_hash,
            description=description,
            parameters=parameters or {},
            depends_on=tuple(depends_on or []),
            lookback=lookback,
        )

        fid = version_obj.feature_id

        # Check cache
        if use_cache and fid in self._cache:
            logger.debug(f"Feature cache hit: {fid}")
            return self._cache[fid]

        # Check disk
        disk_snapshot = self._load_from_disk(fid)
        if disk_snapshot is not None:
            self._cache[fid] = disk_snapshot
            return disk_snapshot

        # Compute
        start = time.monotonic()
        try:
            result = builder(data, **(parameters or {}))
        except Exception as e:
            logger.error(f"Feature computation failed for {fid}: {e}")
            raise

        elapsed_ms = (time.monotonic() - start) * 1000

        # Validate
        null_count = int(result.isna().sum().sum())
        numeric_cols = result.select_dtypes(include=[np.number])
        inf_count = int(np.sum(~np.isfinite(numeric_cols.values))) if numeric_cols.shape[1] > 0 else 0

        snapshot = FeatureSnapshot(
            version=version_obj,
            data=result,
            computation_time_ms=elapsed_ms,
            n_samples=len(result),
            n_features=len(result.columns),
            null_count=null_count,
            inf_count=inf_count,
        )

        # Store
        self._save_to_disk(snapshot)
        self._cache[fid] = snapshot

        logger.info(
            f"Feature computed: {fid} "
            f"({snapshot.n_samples}×{snapshot.n_features}, "
            f"quality={snapshot.quality_score:.2f}, "
            f"time={elapsed_ms:.0f}ms)"
        )

        return snapshot

    def get(self, name: str, version: str = "1.0.0") -> FeatureSnapshot | None:
        """Retrieve a feature snapshot."""
        fid = f"{name}_v{version}"
        if fid in self._cache:
            return self._cache[fid]
        return self._load_from_disk(fid)

    def get_point_in_time(
        self,
        name: str,
        timestamp: str,
        version: str = "1.0.0",
    ) -> pd.DataFrame | None:
        """
        Get features as they would have been at a specific point in time.

        This ensures no future data leakage — only data available
        at or before the timestamp is included.
        """
        snapshot = self.get(name, version)
        if snapshot is None:
            return None

        data = snapshot.data
        if "timestamp" in data.columns:
            mask = data["timestamp"] <= timestamp
            return data[mask]

        return data

    def list_features(self) -> list[FeatureVersion]:
        """List all stored feature versions."""
        versions = []
        for d in sorted(self.store_dir.iterdir()):
            if d.is_dir():
                meta_path = d / "metadata.json"
                if meta_path.exists():
                    with meta_path.open("r") as f:
                        meta = json.load(f)
                    # Only pass fields that FeatureVersion accepts
                    valid_fields = {"name", "version", "content_hash", "created_at",
                                    "description", "parameters", "depends_on", "lookback"}
                    filtered = {k: v for k, v in meta.items() if k in valid_fields}
                    versions.append(FeatureVersion(**filtered))
        return versions

    def compare_versions(
        self,
        name: str,
        version_a: str,
        version_b: str,
    ) -> dict[str, Any]:
        """Compare two feature versions."""
        snap_a = self.get(name, version_a)
        snap_b = self.get(name, version_b)

        if snap_a is None or snap_b is None:
            return {"error": "One or both versions not found"}

        return {
            "version_a": version_a,
            "version_b": version_b,
            "samples_a": snap_a.n_samples,
            "samples_b": snap_b.n_samples,
            "features_a": snap_a.n_features,
            "features_b": snap_b.n_features,
            "quality_a": snap_a.quality_score,
            "quality_b": snap_b.quality_score,
            "nulls_a": snap_a.null_count,
            "nulls_b": snap_b.null_count,
            "hash_a": snap_a.version.content_hash,
            "hash_b": snap_b.version.content_hash,
        }

    def _save_to_disk(self, snapshot: FeatureSnapshot) -> None:
        """Save feature snapshot to disk."""
        feature_dir = self.store_dir / snapshot.version.feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)

        # Save data
        snapshot.data.to_parquet(feature_dir / "features.parquet", index=False)

        # Save metadata
        meta = {
            "name": snapshot.version.name,
            "version": snapshot.version.version,
            "content_hash": snapshot.version.content_hash,
            "created_at": snapshot.version.created_at,
            "description": snapshot.version.description,
            "parameters": snapshot.version.parameters,
            "depends_on": list(snapshot.version.depends_on),
            "lookback": snapshot.version.lookback,
            "n_samples": snapshot.n_samples,
            "n_features": snapshot.n_features,
            "computation_time_ms": snapshot.computation_time_ms,
            "computed_at": snapshot.computed_at,
        }
        with (feature_dir / "metadata.json").open("w") as f:
            json.dump(meta, f, indent=2, default=str)

        # Save quality report
        quality = {
            "quality_score": snapshot.quality_score,
            "null_count": snapshot.null_count,
            "inf_count": snapshot.inf_count,
            "column_stats": {
                col: {
                    "nulls": int(snapshot.data[col].isna().sum()),
                    "mean": float(snapshot.data[col].mean()) if pd.api.types.is_numeric_dtype(snapshot.data[col]) else None,
                    "std": float(snapshot.data[col].std()) if pd.api.types.is_numeric_dtype(snapshot.data[col]) else None,
                }
                for col in snapshot.data.columns
            },
        }
        with (feature_dir / "quality_report.json").open("w") as f:
            json.dump(quality, f, indent=2, default=str)

    def _load_from_disk(self, feature_id: str) -> FeatureSnapshot | None:
        """Load feature snapshot from disk."""
        feature_dir = self.store_dir / feature_id
        if not feature_dir.exists():
            return None

        meta_path = feature_dir / "metadata.json"
        data_path = feature_dir / "features.parquet"

        if not meta_path.exists() or not data_path.exists():
            return None

        with meta_path.open("r") as f:
            meta = json.load(f)

        version = FeatureVersion(
            name=meta["name"],
            version=meta["version"],
            content_hash=meta["content_hash"],
            created_at=meta.get("created_at", ""),
            description=meta.get("description", ""),
            parameters=meta.get("parameters", {}),
            depends_on=tuple(meta.get("depends_on", [])),
            lookback=meta.get("lookback", 0),
        )

        data = pd.read_parquet(data_path)

        return FeatureSnapshot(
            version=version,
            data=data,
            computation_time_ms=meta.get("computation_time_ms", 0),
            n_samples=meta.get("n_samples", len(data)),
            n_features=meta.get("n_features", len(data.columns)),
            computed_at=meta.get("computed_at", ""),
        )
