from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class RunRecord:
    run_id: str
    timestamp: str
    patient_id: str
    config: dict = field(default_factory=dict)
    qc_summary: dict = field(default_factory=dict)
    output_files: list[str] = field(default_factory=list)

class ProjectStore:
    """JSON-based project metadata store."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.project_dir / "project_meta.json"
        self._meta: dict = {}
        if self.meta_path.exists():
            self._meta = json.loads(self.meta_path.read_text())

    @property
    def processed_dir(self) -> Path:
        d = self.project_dir / "processed"
        d.mkdir(exist_ok=True)
        return d

    @property
    def exports_dir(self) -> Path:
        d = self.project_dir / "exports"
        d.mkdir(exist_ok=True)
        return d

    def record_run(self, run: RunRecord) -> None:
        runs = self._meta.setdefault("runs", [])
        runs.append(asdict(run))
        self._save()

    def get_runs(self, patient_id: str | None = None) -> list[dict]:
        runs = self._meta.get("runs", [])
        if patient_id:
            return [r for r in runs if r.get("patient_id") == patient_id]
        return runs

    def set_config(self, key: str, value) -> None:
        self._meta.setdefault("config", {})[key] = value
        self._save()

    def get_config(self, key: str, default=None):
        return self._meta.get("config", {}).get(key, default)

    def _save(self) -> None:
        """Atomic write: write to temp file then replace to avoid corruption."""
        import os
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._meta, indent=2, default=str))
        os.replace(str(tmp), str(self.meta_path))
