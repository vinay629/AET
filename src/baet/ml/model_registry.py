"""Model registry for BAET.

Every trained model is a reproducible artifact with full lineage:
- Training data hash
- Feature set hash
- Parameter hash
- Git commit hash
- Experiment ID
- Validation metrics
- Promotion status (candidate → validated → production → retired)

Models are NEVER loose files. They are versioned, auditable artifacts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelStatus(StrEnum):
    CANDIDATE = "candidate"       # Just trained
    VALIDATED = "validated"       # Passed validation
    PRODUCTION = "production"     # Deployed live
    RETIRED = "retired"           # No longer used
    REJECTED = "rejected"         # Failed validation


@dataclass
class ModelArtifact:
    """A versioned, reproducible model artifact."""
    model_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    version: str = "1.0.0"
    status: ModelStatus = ModelStatus.CANDIDATE

    # Lineage
    experiment_id: str = ""
    training_data_hash: str = ""
    feature_set_hash: str = ""
    feature_names: list[str] = field(default_factory=list)
    parameter_hash: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    git_commit: str = ""

    # Validation
    train_metrics: dict[str, float] = field(default_factory=dict)
    validation_metrics: dict[str, float] = field(default_factory=dict)
    test_metrics: dict[str, float] = field(default_factory=dict)
    leakage_report: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_at: str = ""
    retired_at: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def artifact_id(self) -> str:
        return f"{self.name}_v{self.version}_{self.model_id}"

    @property
    def is_deployable(self) -> bool:
        return self.status in (ModelStatus.VALIDATED, ModelStatus.PRODUCTION)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "experiment_id": self.experiment_id,
            "training_data_hash": self.training_data_hash,
            "feature_set_hash": self.feature_set_hash,
            "feature_names": self.feature_names,
            "parameter_hash": self.parameter_hash,
            "parameters": self.parameters,
            "git_commit": self.git_commit,
            "train_metrics": self.train_metrics,
            "validation_metrics": self.validation_metrics,
            "test_metrics": self.test_metrics,
            "leakage_report": self.leakage_report,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
            "retired_at": self.retired_at,
            "tags": self.tags,
            "notes": self.notes,
        }


class ModelRegistry:
    """
    Registry for all trained models.

    Directory structure:
        models/
        ├── model_id/
        │   ├── artifact.json
        │   ├── model.pkl
        │   └── metadata.json
    """

    def __init__(self, registry_dir: Path) -> None:
        self.registry_dir = registry_dir
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, ModelArtifact] = {}

    def register(
        self,
        name: str,
        parameters: dict[str, Any],
        training_data_hash: str,
        feature_set_hash: str,
        feature_names: list[str],
        experiment_id: str = "",
        tags: list[str] | None = None,
    ) -> ModelArtifact:
        """Register a new model artifact."""
        param_hash = hashlib.sha256(
            json.dumps(parameters, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        git_commit = self._get_git_commit()

        artifact = ModelArtifact(
            name=name,
            experiment_id=experiment_id,
            training_data_hash=training_data_hash,
            feature_set_hash=feature_set_hash,
            feature_names=feature_names,
            parameter_hash=param_hash,
            parameters=parameters,
            git_commit=git_commit,
            tags=tags or [],
        )

        self._artifacts[artifact.artifact_id] = artifact
        self._save_artifact(artifact)

        logger.info(f"Model registered: {artifact.artifact_id}")
        return artifact

    def validate(
        self,
        model_id: str,
        validation_metrics: dict[str, float],
        leakage_report: dict[str, Any] | None = None,
    ) -> None:
        """Mark a model as validated with validation metrics."""
        artifact = self._find(model_id)
        if artifact is None:
            raise ValueError(f"Model not found: {model_id}")

        artifact.validation_metrics = validation_metrics
        if leakage_report:
            artifact.leakage_report = leakage_report

        # Auto-promote if validation passes
        if self._passes_validation(artifact):
            artifact.status = ModelStatus.VALIDATED
            logger.info(f"Model validated: {artifact.artifact_id}")
        else:
            artifact.status = ModelStatus.REJECTED
            logger.warning(f"Model rejected: {artifact.artifact_id}")

        self._save_artifact(artifact)

    def promote(self, model_id: str) -> None:
        """Promote a validated model to production."""
        artifact = self._find(model_id)
        if artifact is None:
            raise ValueError(f"Model not found: {model_id}")

        if artifact.status != ModelStatus.VALIDATED:
            raise ValueError(
                f"Model must be validated before promotion. Current status: {artifact.status.value}"
            )

        artifact.status = ModelStatus.PRODUCTION
        artifact.promoted_at = datetime.now(timezone.utc).isoformat()
        self._save_artifact(artifact)

        logger.info(f"Model promoted to production: {artifact.artifact_id}")

    def retire(self, model_id: str, reason: str = "") -> None:
        """Retire a production model."""
        artifact = self._find(model_id)
        if artifact is None:
            raise ValueError(f"Model not found: {model_id}")

        artifact.status = ModelStatus.RETIRED
        artifact.retired_at = datetime.now(timezone.utc).isoformat()
        artifact.notes += f"\nRetired: {reason}"
        self._save_artifact(artifact)

        logger.info(f"Model retired: {artifact.artifact_id}")

    def get_production_model(self, name: str) -> ModelArtifact | None:
        """Get the current production model for a given name."""
        for artifact in self._artifacts.values():
            if artifact.name == name and artifact.status == ModelStatus.PRODUCTION:
                return artifact
        return None

    def list_models(
        self,
        name: str | None = None,
        status: ModelStatus | None = None,
    ) -> list[ModelArtifact]:
        """List models, optionally filtered."""
        results = list(self._artifacts.values())
        if name:
            results = [a for a in results if a.name == name]
        if status:
            results = [a for a in results if a.status == status]
        return sorted(results, key=lambda a: a.created_at, reverse=True)

    def compare_models(
        self,
        model_ids: list[str],
        metric: str = "sharpe_ratio",
    ) -> list[dict[str, Any]]:
        """Compare models by a specific metric."""
        rows = []
        for mid in model_ids:
            artifact = self._find(mid)
            if artifact is None:
                continue
            metrics = {**artifact.validation_metrics, **artifact.test_metrics}
            rows.append({
                "model_id": artifact.model_id,
                "name": artifact.name,
                "version": artifact.version,
                "status": artifact.status.value,
                metric: metrics.get(metric, 0),
            })
        return sorted(rows, key=lambda r: r.get(metric, 0), reverse=True)

    def _passes_validation(self, artifact: ModelArtifact) -> bool:
        """Check if a model passes validation criteria."""
        metrics = artifact.validation_metrics

        # Basic criteria
        if metrics.get("sharpe_ratio", 0) < 0.5:
            return False
        if metrics.get("max_drawdown_pct", 100) > 30:
            return False

        # Leakage check
        leakage = artifact.leakage_report
        if leakage and not leakage.get("passed", True):
            return False

        return True

    def _find(self, model_id: str) -> ModelArtifact | None:
        """Find a model by ID (checks memory and disk)."""
        # Check memory
        for artifact in self._artifacts.values():
            if artifact.model_id == model_id:
                return artifact

        # Check disk
        for d in self.registry_dir.iterdir():
            if d.is_dir():
                artifact_path = d / "artifact.json"
                if artifact_path.exists():
                    with artifact_path.open("r") as f:
                        data = json.load(f)
                    if data.get("model_id") == model_id:
                        return self._from_dict(data)

        return None

    def _save_artifact(self, artifact: ModelArtifact) -> None:
        """Save artifact to disk."""
        artifact_dir = self.registry_dir / artifact.artifact_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        with (artifact_dir / "artifact.json").open("w") as f:
            json.dump(artifact.to_dict(), f, indent=2, default=str)

    def _from_dict(self, data: dict[str, Any]) -> ModelArtifact:
        """Reconstruct artifact from dict."""
        return ModelArtifact(
            model_id=data["model_id"],
            name=data["name"],
            version=data["version"],
            status=ModelStatus(data["status"]),
            experiment_id=data.get("experiment_id", ""),
            training_data_hash=data.get("training_data_hash", ""),
            feature_set_hash=data.get("feature_set_hash", ""),
            feature_names=data.get("feature_names", []),
            parameter_hash=data.get("parameter_hash", ""),
            parameters=data.get("parameters", {}),
            git_commit=data.get("git_commit", ""),
            train_metrics=data.get("train_metrics", {}),
            validation_metrics=data.get("validation_metrics", {}),
            test_metrics=data.get("test_metrics", {}),
            leakage_report=data.get("leakage_report", {}),
            created_at=data.get("created_at", ""),
            promoted_at=data.get("promoted_at", ""),
            retired_at=data.get("retired_at", ""),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )

    @staticmethod
    def _get_git_commit() -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
