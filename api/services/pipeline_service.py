"""Wraps qeeg.pipeline for the API layer. Manages patient results in memory + disk cache."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from qeeg.config import PipelineConfig, ArtifactConfig, SeizureConfig, BinningConfig
from qeeg.pipeline import PatientResult, process_patient, concatenate_and_process
from qeeg.ingestion.parser import parse_persyst_csv
from qeeg.ingestion.quick_scan import quick_scan
from qeeg.ingestion.column_mapper import ColumnEntry
from qeeg.ingestion.mmx_parser import EngineConfig
from qeeg.storage.result_cache import (
    content_hash_files, save_result, load_result, list_cached_patients,
    load_patient_meta,
)

log = logging.getLogger(__name__)

MAX_HOT_PATIENTS = 10  # max patients with DataFrames in hot cache


def _parse_clock_time(value: str) -> tuple[int, int, float] | None:
    """Parse a clock-time string into (hours, minutes, seconds).

    Tolerant of HH:MM, HH:MM:SS, HH:MM:SS.ffffff, and optional trailing AM/PM.
    Returns None if parsing fails.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    suffix = None
    upper = s.upper()
    for mark in (" AM", " PM", "AM", "PM"):
        if upper.endswith(mark):
            suffix = mark.strip()
            s = s[: -len(mark)].strip()
            break
    parts = s.split(":")
    if len(parts) < 2 or len(parts) > 3:
        return None
    try:
        h = int(parts[0])
        m = int(parts[1])
        sec = float(parts[2]) if len(parts) == 3 else 0.0
    except ValueError:
        return None
    if suffix == "PM" and h < 12:
        h += 12
    elif suffix == "AM" and h == 12:
        h = 0
    return (h, m, sec)


@dataclass
class StudyConfig:
    """A named study with an associated MMX configuration."""
    name: str
    mmx_study: Optional[str] = None  # references an MMX config name
    created_at: Optional[str] = None
    date_shifted: bool = False  # True if dates are de-identified via shifting


@dataclass
class ClinicalMetadata:
    """Patient clinical metadata from external CSV.

    Accepts ROSC as combined rosc_datetime OR separate rosc_date + rosc_time.
    The effective_rosc_datetime property resolves whichever is available.
    """
    patient_id: str
    rosc_time: Optional[str] = None       # HH:MM:SS — always required in practice
    age_at_arrest_days: Optional[int] = None  # required when dates are shifted; omit when rosc_date is provided
    rosc_datetime: Optional[str] = None   # ISO format combined datetime
    rosc_date: Optional[str] = None       # YYYY-MM-DD — provide for non-date-shifted data
    sex: Optional[str] = None
    arrest_etiology: Optional[str] = None
    site: Optional[str] = None
    primary_outcome_pcpc: Optional[int] = None
    secondary_outcome_vabs: Optional[str] = None
    notes: Optional[str] = None

    @property
    def effective_rosc_datetime(self) -> Optional[str]:
        """Resolve ROSC datetime from combined or separate fields."""
        if self.rosc_datetime:
            return self.rosc_datetime
        if self.rosc_date and self.rosc_time:
            return f"{self.rosc_date} {self.rosc_time}"
        return None

    @property
    def age_days(self) -> Optional[int]:
        return self.age_at_arrest_days


@dataclass
class EEGCorrection:
    """EEG date correction entry mapping de-identified filename to actual timing."""
    new_name: str               # matches file stem (e.g. "4290-1_1684730")
    age_in_days_at_time_of_eeg: int
    eeg_start_time: str         # HH:MM:SS clock time
    eeg_duration: str           # HH:MM:SS
    date_of_csv_creation: Optional[str] = None


@dataclass
class PatientMeta:
    """Tier-1: lightweight patient index entry. ~2-5KB per patient.

    Loaded from meta.json + schema.json on startup. No DataFrames.
    """
    patient_id: str
    cache_dir: Path
    schema: list  # list[ColumnEntry]
    qc: object  # QCReport
    seizure_report: object  # SeizureReport
    time_info: object  # TimeAxisInfo
    artifact_result_summary: dict
    validation_summary: dict
    warnings: list[str]
    n_epochs: int
    n_bins: int
    source_files: list[str]
    content_hash: str
    stage_row_counts: dict = field(default_factory=dict)


@dataclass
class CachedFrames:
    """Tier-2: hot DataFrame cache entry for a patient.

    ``epochs`` accumulates columns across selective loads — each call to
    ``_get_or_load_frames`` with a ``columns`` list unions the newly-read
    columns into the existing DataFrame rather than replacing it, so
    earlier loads are not invalidated by a panel asking for a different
    family. ``bin_summary`` lives in a separate, non-evicted cache.
    """
    epochs: Optional[pd.DataFrame] = None
    bin_summary: Optional[pd.DataFrame] = None
    loaded_columns: set = field(default_factory=set)
    full_load: bool = False  # True only when all parquet columns were loaded
    last_access: float = field(default_factory=time.time)


def _user_friendly_error(exc: Exception) -> str:
    """Convert technical exceptions to user-actionable messages."""
    msg = str(exc)
    exc_type = type(exc).__name__

    if isinstance(exc, KeyError):
        return f"Missing expected data column: {msg}. Check that your Persyst CSV is complete."
    if isinstance(exc, MemoryError) or "memory" in msg.lower():
        return "Out of memory processing this file. Try running one patient at a time."
    if isinstance(exc, FileNotFoundError):
        return f"Data file not found: {msg}. Re-upload the file and try again."
    if "UnicodeDecodeError" in exc_type or isinstance(exc, UnicodeDecodeError):
        return "File encoding error. Ensure the CSV was exported from Persyst without special characters."
    if "EmptyDataError" in exc_type:
        return "The uploaded CSV appears empty or has no data rows."
    if "ParserError" in exc_type:
        return "Could not parse the CSV. Verify the file is a valid Persyst export."
    # Fallback: include type but not full traceback
    return f"Processing error ({exc_type}). See server logs for details."

# Persistent disk cache directory (stored with the app, not with source files)
from qeeg.paths import CACHE_DIR


@dataclass
class JobStatus:
    job_id: str
    patient_id: str
    stage: str = "queued"
    progress: float = 0.0
    message: str = ""
    complete: bool = False
    error: Optional[str] = None
    started_at: float = field(default_factory=lambda: time.time())
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


class PipelineService:
    """Singleton service managing pipeline execution and result caching.

    Two-tier lazy-loading architecture:
    1. Patient index (dict[str, PatientMeta]) — lightweight metadata for ALL cached
       patients, loaded from meta.json + schema.json on startup. No size limit.
    2. Hot cache (OrderedDict[str, CachedFrames]) — LRU cache of recently-accessed
       DataFrames, lazy-loaded from parquet on demand. Bounded to MAX_HOT_PATIENTS.
    3. Disk cache at .qeeg_cache/ (persistent, content-hash-based)

    Content-based hashing means the same file imported from any location
    hits the cache as long as file contents + pipeline config match.
    """

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._patient_index: dict[str, PatientMeta] = {}               # Tier 1: all patients
        self._hot_cache: OrderedDict[str, CachedFrames] = OrderedDict()  # Tier 2: LRU
        self._bin_summary_cache: dict[str, pd.DataFrame] = {}           # tiny, never evicted
        self._jobs: dict[str, JobStatus] = {}
        self._clinical_metadata: dict[str, ClinicalMetadata] = {}  # patient_id -> metadata
        self._eeg_corrections: dict[str, EEGCorrection] = {}       # new_name -> correction
        self._mmx_configs: dict[str, dict] = {}                    # study_name -> {engines, fingerprint, source_path}
        self._studies: dict[str, StudyConfig] = {}                   # study_name -> StudyConfig
        self._patient_studies: dict[str, str] = {}                   # patient_id -> study_name
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)  # 2 workers for N150 memory
        self._load_persistent_data()

    # -- Persistence helpers --

    @property
    def _clinical_path(self) -> Path:
        return self.cache_dir / "clinical_metadata.json"

    @property
    def _corrections_path(self) -> Path:
        return self.cache_dir / "eeg_corrections.json"

    @property
    def _mmx_configs_path(self) -> Path:
        return self.cache_dir / "mmx_configs.json"

    @property
    def _studies_path(self) -> Path:
        return self.cache_dir / "studies.json"

    @property
    def _patient_studies_path(self) -> Path:
        return self.cache_dir / "patient_studies.json"

    def _load_persistent_data(self) -> None:
        """Load clinical metadata and EEG corrections from disk on startup."""
        if self._clinical_path.exists():
            try:
                raw = json.loads(self._clinical_path.read_text(encoding="utf-8"))
                self._clinical_metadata = {}
                for pid, v in raw.items():
                    # Backward compat: old cache used "age_days", new uses "age_at_arrest_days"
                    if "age_days" in v and "age_at_arrest_days" not in v:
                        v["age_at_arrest_days"] = v.pop("age_days")
                    self._clinical_metadata[pid] = ClinicalMetadata(**v)
                log.info("Loaded clinical metadata for %d patients from disk", len(self._clinical_metadata))
            except Exception as e:
                log.warning("Could not load clinical metadata: %s", e)

        if self._corrections_path.exists():
            try:
                raw = json.loads(self._corrections_path.read_text(encoding="utf-8"))
                self._eeg_corrections = {
                    name: EEGCorrection(**v) for name, v in raw.items()
                }
                log.info("Loaded EEG corrections for %d files from disk", len(self._eeg_corrections))
            except Exception as e:
                log.warning("Could not load EEG corrections: %s", e)

        if self._mmx_configs_path.exists():
            try:
                raw = json.loads(self._mmx_configs_path.read_text(encoding="utf-8"))
                for study_name, cfg in raw.items():
                    engines = {
                        name: EngineConfig(name=name, epoch_duration=ec["epoch_duration"], epoch_step=ec["epoch_step"])
                        for name, ec in cfg["engines"].items()
                    }
                    self._mmx_configs[study_name] = {
                        "engines": engines,
                        "fingerprint": cfg["fingerprint"],
                        "source_path": cfg.get("source_path", ""),
                    }
                log.info("Loaded MMX configs for %d studies from disk", len(self._mmx_configs))
            except Exception as e:
                log.warning("Could not load MMX configs: %s", e)

        if self._studies_path.exists():
            try:
                raw = json.loads(self._studies_path.read_text(encoding="utf-8"))
                self._studies = {name: StudyConfig(**v) for name, v in raw.items()}
                log.info("Loaded %d studies from disk", len(self._studies))
            except Exception as e:
                log.warning("Could not load studies: %s", e)

        if self._patient_studies_path.exists():
            try:
                self._patient_studies = json.loads(self._patient_studies_path.read_text(encoding="utf-8"))
                log.info("Loaded study assignments for %d patients from disk", len(self._patient_studies))
            except Exception as e:
                log.warning("Could not load patient study assignments: %s", e)

        # Build patient index from all cached results on disk
        self._build_patient_index()

    # -- Reconstruction helpers (shared by index build + cache-hit path) --

    @staticmethod
    def _reconstruct_schema(schema_raw: list[dict]) -> list:
        """Reconstruct list[ColumnEntry] from cached JSON."""
        schema = []
        for entry in schema_raw:
            schema.append(ColumnEntry(
                col_index=entry["col_index"], code=entry["code"],
                i_group=entry["i_group"], sub_index=entry["sub_index"],
                trend_name=entry["trend_name"], family=entry["family"],
                frequency_band=entry["frequency_band"],
                freq_min_hz=entry.get("freq_min_hz"),
                freq_max_hz=entry.get("freq_max_hz"),
                hemisphere=entry["hemisphere"], region=entry["region"],
                electrode=entry["electrode"],
                sub_column_name=entry.get("sub_column_name", ""),
                common_name=entry.get("common_name", ""),
            ))
        return schema

    @staticmethod
    def _reconstruct_qc(meta: dict, patient_id: str):
        """Reconstruct QCReport from cached meta dict."""
        from qeeg.quality.qc_report import QCReport
        qc_data = meta["qc"]
        return QCReport(
            patient_id=patient_id,
            total_epochs=qc_data.get("total_epochs", 0),
            usable_epochs=qc_data.get("usable_epochs", 0),
            artifact_pct=qc_data.get("artifact_pct", 0),
            seizure_epochs=qc_data.get("seizure_epochs", 0),
            seizure_pct_of_total=qc_data.get("seizure_pct_of_total", 0),
            recording_duration_hours=qc_data.get("recording_duration_hours", 0),
            usable_hours=qc_data.get("usable_hours", 0),
            median_suppression_pct=qc_data.get("median_suppression_pct"),
            bin_coverage=qc_data.get("bin_coverage", {}),
            warnings=qc_data.get("warnings", []),
        )

    @staticmethod
    def _reconstruct_seizure_report(meta: dict):
        """Reconstruct SeizureReport from cached meta dict."""
        from qeeg.analysis.seizure import SeizureReport
        sz_data = meta["seizure_report"]
        return SeizureReport(
            total_seizure_epochs=sz_data.get("total_seizure_epochs", 0),
            seizure_burden_pct=sz_data.get("seizure_burden_pct", 0),
            max_seizure_probability=sz_data.get("max_seizure_probability", 0),
            seizure_events=sz_data.get("seizure_events", 0),
            max_hourly_burden_pct=sz_data.get("max_hourly_burden_pct", 0),
            has_status_epilepticus=sz_data.get(
                "has_status_epilepticus",
                sz_data.get("status_epilepticus_screen_flag", False),
            ),
            longest_seizure_minutes=sz_data.get("longest_seizure_minutes", 0),
            time_to_first_seizure_hours=sz_data.get("time_to_first_seizure_hours"),
            per_bin_burden=sz_data.get("per_bin_burden", {}),
        )

    @staticmethod
    def _reconstruct_time_info(meta: dict):
        """Reconstruct TimeAxisInfo from cached meta dict."""
        from qeeg.alignment.time_axis import TimeAxisInfo
        ti_data = meta["time_info"]
        ref_time = pd.Timestamp(ti_data["reference_time"]) if ti_data.get("reference_time") else pd.NaT
        return TimeAxisInfo(reference=ti_data.get("reference", "recording_start"), reference_time=ref_time)

    @staticmethod
    def _cache_candidate_rank(meta: dict, clinical_present: bool, dir_mtime: float) -> tuple[int, int, int, float]:
        """Rank duplicate patient caches by scientific context before recency.

        Reprocesses or stale caches can leave multiple cache directories for the
        same patient. Recency alone is unsafe: a newer cache may have lost ROSC
        or correction context and inflate the timebase. Prefer caches that use
        available clinical time context and stay within the configured analysis
        horizon; use mtime only as a final tie-breaker.
        """
        time_ref = (meta.get("time_info") or {}).get("reference")
        qc = meta.get("qc") or {}
        config = meta.get("config") or {}
        binning = config.get("binning") or {}

        if clinical_present:
            context_score = 1 if time_ref == "rosc" else 0
        else:
            context_score = 1

        try:
            duration = float(qc.get("recording_duration_hours", 0.0) or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        try:
            max_hours = float(binning.get("max_hours", 168.0) or 168.0)
        except (TypeError, ValueError):
            max_hours = 168.0
        duration_score = 1 if duration <= max_hours else 0

        try:
            gap_count = int(qc.get("timestamp_gaps", 0) or 0)
        except (TypeError, ValueError):
            gap_count = 0
        gap_score = -gap_count

        return (context_score, duration_score, gap_score, dir_mtime)

    def _build_patient_index(self) -> None:
        """Scan .qeeg_cache/ and build in-memory index from meta.json + schema.json.

        Handles duplicate patient_ids by keeping the most scientifically
        contextual cache, then the newest as a tie-breaker.
        """
        seen: dict[str, tuple[tuple[int, int, int, float], PatientMeta]] = {}

        if not self.cache_dir.exists():
            return

        for patient_dir in self.cache_dir.iterdir():
            if not patient_dir.is_dir():
                continue
            loaded = load_patient_meta(patient_dir)
            if loaded is None:
                continue
            try:
                meta = loaded["meta"]
                pid = meta["patient_id"]

                schema = self._reconstruct_schema(loaded["schema"])
                qc = self._reconstruct_qc(meta, pid)
                seizure_report = self._reconstruct_seizure_report(meta)
                time_info = self._reconstruct_time_info(meta)

                entry = PatientMeta(
                    patient_id=pid,
                    cache_dir=patient_dir,
                    schema=schema,
                    qc=qc,
                    seizure_report=seizure_report,
                    time_info=time_info,
                    artifact_result_summary=meta.get("artifact_result", {}),
                    validation_summary=meta.get("validation", {}),
                    warnings=meta.get("warnings", []),
                    n_epochs=meta.get("n_epochs", 0),
                    n_bins=meta.get("n_bins", 0),
                    source_files=meta.get("source_files", []),
                    content_hash=meta.get("content_hash", ""),
                    stage_row_counts=meta.get("stage_row_counts", {}) or {},
                )

                dir_mtime = patient_dir.stat().st_mtime
                rank = self._cache_candidate_rank(
                    meta,
                    clinical_present=pid in self._clinical_metadata,
                    dir_mtime=dir_mtime,
                )
                if pid not in seen or rank > seen[pid][0]:
                    seen[pid] = (rank, entry)

            except Exception as e:
                log.warning("Skipping cache dir %s: %s", patient_dir.name, e)
                continue

        self._patient_index = {pid: entry for pid, (_, entry) in seen.items()}
        log.info("Patient index built: %d patients from disk cache", len(self._patient_index))
        self._reconcile_patient_studies()

    def _reconcile_patient_studies(self) -> None:
        """Drop _patient_studies entries whose patient_id is not in _patient_index."""
        with self._lock:
            orphans = [pid for pid in self._patient_studies if pid not in self._patient_index]
        if orphans:
            with self._lock:
                for pid in orphans:
                    self._patient_studies.pop(pid, None)
            self._save_patient_studies()
            log.info("Reconciled _patient_studies: removed %d orphan entries %s", len(orphans), orphans)

    # -- Tier 2: Hot cache with lazy loading --

    def _get_or_load_bin_summary(
        self, patient_id: str, meta: PatientMeta
    ) -> Optional[pd.DataFrame]:
        """Return the cached bin_summary DataFrame, loading once from parquet.

        bin_summary files are tiny (<100KB) so we keep them in a separate
        dict that is never evicted by the epochs LRU.
        """
        with self._lock:
            bs = self._bin_summary_cache.get(patient_id)
        if bs is not None:
            return bs

        bin_path = meta.cache_dir / "bin_summary.parquet"
        if not bin_path.exists():
            return None
        try:
            from qeeg.storage.parquet_io import load_epochs_columns
            bs = load_epochs_columns(bin_path)
        except Exception as e:
            log.warning("Failed to load bin_summary for %s: %s", patient_id, e)
            return None

        with self._lock:
            self._bin_summary_cache[patient_id] = bs
        return bs

    def _get_or_load_frames(
        self, patient_id: str, meta: PatientMeta,
        columns: list[str] | None = None,
    ) -> Optional[CachedFrames]:
        """Load DataFrames from hot cache or parquet, column-selective.

        On a partial cache hit (some requested columns missing) this reads
        ONLY the missing columns from parquet and UNIONs them into the
        already-cached DataFrame — earlier loads are preserved so switching
        panels does not invalidate previously-loaded columns.

        Args:
            columns: epoch columns to ensure are loaded. None = all columns.
        """
        from qeeg.storage.parquet_io import load_epochs_columns

        epochs_path = meta.cache_dir / "epochs.parquet"
        if not epochs_path.exists():
            log.warning("Parquet file missing for %s at %s", patient_id, epochs_path)
            return None

        # Ensure bin_summary is loaded into its own (non-evicted) cache.
        bin_summary = self._get_or_load_bin_summary(patient_id, meta)
        if bin_summary is None:
            return None

        # Fast path: full cache hit + snapshot for partial-hit path.
        # We snapshot epochs + loaded_columns under the lock so the slow disk
        # I/O below operates on a stable reference even if another thread
        # evicts/replaces the hot-cache entry mid-flight.
        cached_epochs: Optional[pd.DataFrame] = None
        cached_loaded: set[str] = set()
        cached_full_load = False
        with self._lock:
            cached = self._hot_cache.get(patient_id)
            if cached is not None and cached.epochs is not None:
                self._hot_cache.move_to_end(patient_id)
                # full_load=True means ALL columns were loaded — satisfies any request.
                # Otherwise hit only if every requested column is already in the cache.
                if cached.full_load or \
                        (columns is not None and set(columns).issubset(cached.loaded_columns)):
                    cached.last_access = time.time()
                    cached.bin_summary = bin_summary
                    return cached
                cached_epochs = cached.epochs
                cached_loaded = set(cached.loaded_columns)
                cached_full_load = cached.full_load

        try:
            if cached_epochs is None:
                epochs = load_epochs_columns(epochs_path, columns=columns)
                frames = CachedFrames(
                    epochs=epochs,
                    bin_summary=bin_summary,
                    loaded_columns=set(epochs.columns),
                    full_load=columns is None,
                )
            else:
                if columns is None:
                    # Caller wants everything but cache is partial — reload the
                    # full parquet rather than handing back a partial DataFrame.
                    combined = load_epochs_columns(epochs_path, columns=None)
                    full_load = True
                else:
                    missing = [c for c in columns if c not in cached_loaded]
                    if missing:
                        new_df = load_epochs_columns(epochs_path, columns=missing)
                        combined = pd.concat(
                            [cached_epochs.reset_index(drop=True),
                             new_df.reset_index(drop=True)],
                            axis=1,
                        )
                    else:
                        combined = cached_epochs
                    full_load = cached_full_load
                frames = CachedFrames(
                    epochs=combined,
                    bin_summary=bin_summary,
                    loaded_columns=set(combined.columns),
                    full_load=full_load,
                )

            with self._lock:
                self._hot_cache[patient_id] = frames
                self._hot_cache.move_to_end(patient_id)
                while len(self._hot_cache) > MAX_HOT_PATIENTS:
                    evicted_pid, _ = self._hot_cache.popitem(last=False)
                    log.debug("Evicted %s from hot cache", evicted_pid)

            return frames

        except Exception as e:
            log.warning("Failed to load parquet for %s: %s", patient_id, e)
            return None

    def remove_patient(self, patient_id: str) -> None:
        """Remove a patient from index, hot cache, and persistent sidecar state.

        Clears the in-memory index/hot-cache entries AND the persistent
        `_patient_studies` + `_clinical_metadata` dicts, then persists both
        JSON files so the patient does not reappear on server restart.
        """
        with self._lock:
            self._patient_index.pop(patient_id, None)
            self._hot_cache.pop(patient_id, None)
            self._bin_summary_cache.pop(patient_id, None)
            studies_dirty = self._patient_studies.pop(patient_id, None) is not None
            clinical_dirty = self._clinical_metadata.pop(patient_id, None) is not None
        if studies_dirty:
            self._save_patient_studies()
        if clinical_dirty:
            self._save_clinical_metadata()

    def _save_clinical_metadata(self) -> None:
        try:
            self._clinical_path.write_text(
                json.dumps({pid: asdict(m) for pid, m in self._clinical_metadata.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Could not persist clinical metadata: %s", e)

    def _save_eeg_corrections(self) -> None:
        try:
            self._corrections_path.write_text(
                json.dumps({name: asdict(c) for name, c in self._eeg_corrections.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Could not persist EEG corrections: %s", e)

    def _save_studies(self) -> None:
        try:
            self._studies_path.write_text(
                json.dumps({name: asdict(s) for name, s in self._studies.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Could not persist studies: %s", e)

    def _save_patient_studies(self) -> None:
        try:
            self._patient_studies_path.write_text(
                json.dumps(self._patient_studies, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Could not persist patient study assignments: %s", e)

    def get_upload_path(self, file_id: str) -> Path:
        """Resolve a file_id to the actual file path.

        Handles two modes:
        - Direct upload: file exists at upload_dir/file_id
        - Local path pointer: a .ptr file contains the real path on disk
        """
        direct = self.upload_dir / file_id
        if direct.exists():
            return direct
        # Check for pointer file (from /upload/local endpoint)
        ptr = self.upload_dir / f"{file_id}.ptr"
        if not ptr.exists():
            # Try with .ptr suffix already in file_id
            ptr = direct.with_suffix(".ptr")
        if ptr.exists():
            real_path = Path(ptr.read_text(encoding="utf-8").strip())
            if real_path.exists():
                return real_path
        return direct  # fallback

    # -- Job management --

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        return self._jobs.get(job_id)

    def run_pipeline(
        self,
        file_ids: list[str],
        patient_id: str,
        config: PipelineConfig,
        rosc_time_str: Optional[str] = None,
        mmx_study: Optional[str] = None,
        study_name: Optional[str] = None,
    ) -> JobStatus:
        job_id = str(uuid.uuid4())[:8]
        status = JobStatus(job_id=job_id, patient_id=patient_id)
        self._jobs[job_id] = status

        # Inject clinical metadata if available and rosc_time not already set
        if rosc_time_str is None:
            clinical = self.get_clinical_metadata(patient_id)
            if clinical and clinical.effective_rosc_datetime:
                rosc_time_str = clinical.effective_rosc_datetime

        self._executor.submit(
            self._run_in_thread, job_id, file_ids, patient_id, config, rosc_time_str, mmx_study, study_name
        )
        return status

    def _run_in_thread(
        self,
        job_id: str,
        file_ids: list[str],
        patient_id: str,
        config: PipelineConfig,
        rosc_time_str: Optional[str],
        mmx_study: Optional[str] = None,
        study_name: Optional[str] = None,
    ):
        status = self._jobs[job_id]
        STAGES = [
            "Parsing CSV", "Processing timestamps", "Validating data",
            "Aligning to ROSC", "Filtering artifacts", "Detecting seizures",
            "Computing features", "Binning by time", "QC Report", "Finalizing",
        ]
        stage_index = [0]

        try:
            paths = [self.get_upload_path(fid) for fid in file_ids]

            # All CSV types are now processed together — multi-panel CSVs
            # (time_averages containing RAV/ADR/Power-by-Band) are merged by
            # semantic column name via merge_segments_by_semantic_name.
            # Log panel types as diagnostic metadata only.
            for p in paths:
                try:
                    panel = quick_scan(p).csv_panel_type
                    if panel not in ("trends", ""):
                        log.debug("Patient %s: CSV %s has panel type %r — will be merged", patient_id, p.name, panel)
                except Exception:
                    pass

            config_dict = config.model_dump()

            # Build extra cache key components from clinical metadata and corrections
            # so that uploading new corrections or clinical data triggers reprocessing.
            _clinical = self.get_clinical_metadata(patient_id)
            clinical_meta_dict = asdict(_clinical) if _clinical else None
            _relevant_corr = self._relevant_corrections_for_paths(paths)
            eeg_corrections_dict = _relevant_corr if _relevant_corr else None

            # Resolve MMX — load full MMXConfig from source_path for MMX-first column resolution
            mmx_cfg = self.get_mmx_config(mmx_study) if mmx_study else None
            mmx_engines = mmx_cfg["engines"] if mmx_cfg else None
            mmx_fingerprint = mmx_cfg["fingerprint"] if mmx_cfg else None
            full_mmx = None
            if mmx_cfg and mmx_cfg.get("source_path"):
                try:
                    from qeeg.ingestion.mmx_parser import parse_mmx
                    full_mmx = parse_mmx(mmx_cfg["source_path"])
                    log.debug("Loaded full MMXConfig from %s", mmx_cfg["source_path"])
                except Exception as e:
                    log.warning("Could not load full MMXConfig from %s: %s", mmx_cfg.get("source_path"), e)
            # Build a hashable dict for cache key
            mmx_cache_dict = None
            if mmx_engines:
                mmx_cache_dict = {
                    "fingerprint": mmx_fingerprint,
                    "source_path": mmx_cfg.get("source_path", "") if mmx_cfg else "",
                    "engines": {
                        name: {"epoch_duration": ec.epoch_duration, "epoch_step": ec.epoch_step}
                        for name, ec in mmx_engines.items()
                    },
                }

            # ── Check disk cache (content-based) ─────────────────────
            with status._lock:
                status.stage = "Checking cache"
                status.message = "Hashing file contents..."
                status.progress = 0.0

            file_content_hash = content_hash_files(paths)
            cached = load_result(file_content_hash, config_dict, self.cache_dir,
                                 clinical_meta=clinical_meta_dict,
                                 eeg_corrections=eeg_corrections_dict,
                                 mmx_config=mmx_cache_dict)

            if cached is not None:
                # Cache hit — populate both tiers from disk
                with status._lock:
                    status.stage = "Loading from cache"
                    status.progress = 0.9
                    status.message = "Cache hit — loading saved results"
                log.info("Disk cache hit for %s (hash: %s…)", patient_id, file_content_hash[:12])

                meta = cached["meta"]
                schema = self._reconstruct_schema(cached.get("schema", []))
                qc = self._reconstruct_qc(meta, patient_id)
                seizure_report = self._reconstruct_seizure_report(meta)
                time_info = self._reconstruct_time_info(meta)

                # Find the cache directory from the content hash
                cache_dir = None
                for d in self.cache_dir.iterdir():
                    if d.is_dir() and d.name.startswith(file_content_hash[:12]):
                        cache_dir = d
                        break
                if cache_dir is None:
                    cache_dir = self.cache_dir  # fallback

                # Tier 1: update index
                idx_entry = PatientMeta(
                    patient_id=patient_id,
                    cache_dir=cache_dir,
                    schema=schema,
                    qc=qc,
                    seizure_report=seizure_report,
                    time_info=time_info,
                    artifact_result_summary=meta.get("artifact_result", {}),
                    validation_summary=meta.get("validation", {}),
                    warnings=meta.get("warnings", []),
                    n_epochs=meta.get("n_epochs", 0),
                    n_bins=meta.get("n_bins", 0),
                    source_files=meta.get("source_files", []),
                    content_hash=meta.get("content_hash", ""),
                    stage_row_counts=meta.get("stage_row_counts", {}) or {},
                )

                # Tier 2: warm hot cache with already-loaded DataFrames
                frames = CachedFrames(
                    epochs=cached["epochs"],
                    bin_summary=cached["bin_summary"],
                    loaded_columns=set(cached["epochs"].columns),
                    full_load=True,
                )

                with self._lock:
                    self._patient_index[patient_id] = idx_entry
                    self._hot_cache[patient_id] = frames
                    self._hot_cache.move_to_end(patient_id)
                    self._bin_summary_cache[patient_id] = cached["bin_summary"]
                    while len(self._hot_cache) > MAX_HOT_PATIENTS:
                        self._hot_cache.popitem(last=False)

                with status._lock:
                    status.stage = "complete"
                    status.progress = 1.0
                    status.complete = True
                    status.message = "Loaded from cache (instant)"
                return

            # ── No cache hit — run full pipeline ─────────────────────
            def progress_cb(stage: str, frac: float):
                try:
                    idx = next(i for i, s in enumerate(STAGES) if s.lower() in stage.lower())
                    stage_index[0] = idx
                except StopIteration:
                    idx = stage_index[0]
                cumulative = (idx + frac) / len(STAGES)
                with status._lock:
                    status.stage = stage
                    status.progress = cumulative
                    status.message = f"{stage} ({cumulative:.0%})"

            # ── Apply EEG date corrections (reorder segments by actual time) ──
            if len(paths) > 1:
                paths = self._sort_paths_by_corrections(paths)

            # ── Replace de-identified timestamps with synthetic ones ──
            corrected_parsed, synthetic_rosc = self._apply_date_corrections(
                paths, patient_id
            )

            if corrected_parsed is not None:
                # Date-corrected path: timestamps already replaced, ROSC will align
                rosc_time_str = synthetic_rosc
                if len(corrected_parsed) == 1:
                    result = process_patient(
                        paths[0], config=config, patient_id=patient_id,
                        rosc_time_str=rosc_time_str, progress_cb=progress_cb,
                        parsed=corrected_parsed[0],
                        mmx_engines=mmx_engines, mmx=full_mmx,
                    )
                else:
                    # Multi-segment: merge by semantic column name (common_name)
                    # rather than raw I-code to avoid cross-segment collisions.
                    from qeeg.ingestion.segment_merge import (
                        merge_segments_by_semantic_name,
                    )
                    merged_parsed, merged_schema = merge_segments_by_semantic_name(
                        corrected_parsed, mmx=full_mmx
                    )
                    if "ClockDateTime" in merged_parsed.data.columns:
                        merged_parsed.data = (
                            merged_parsed.data
                            .sort_values("ClockDateTime")
                            .reset_index(drop=True)
                        )
                    result = process_patient(
                        paths[0], config=config, patient_id=patient_id,
                        rosc_time_str=rosc_time_str, progress_cb=progress_cb,
                        parsed=merged_parsed,
                        mmx_engines=mmx_engines,
                        mmx=full_mmx,
                        pre_built_schema=merged_schema,
                    )
            elif len(paths) == 1:
                result = process_patient(
                    paths[0], config=config, patient_id=patient_id,
                    rosc_time_str=rosc_time_str, progress_cb=progress_cb,
                    mmx_engines=mmx_engines, mmx=full_mmx,
                )
            else:
                result = concatenate_and_process(
                    paths, config=config, patient_id=patient_id,
                    rosc_time_str=rosc_time_str, progress_cb=progress_cb,
                    mmx_engines=mmx_engines, mmx=full_mmx,
                )

            # Save to disk cache for future reuse
            cache_dir_path = None
            try:
                cache_dir_path = save_result(result, config_dict, file_content_hash,
                           [str(p) for p in paths], self.cache_dir,
                           clinical_meta=clinical_meta_dict,
                           eeg_corrections=eeg_corrections_dict,
                           mmx_config=mmx_cache_dict)
            except Exception as e:
                log.warning("Failed to save cache for %s: %s", patient_id, e)

            # Tier 1: update patient index
            idx_entry = PatientMeta(
                patient_id=patient_id,
                cache_dir=cache_dir_path or self.cache_dir,
                schema=result.schema,
                qc=result.qc,
                seizure_report=result.seizure_report,
                time_info=result.time_info,
                artifact_result_summary={
                    "total_epochs": result.artifact_result.total_epochs,
                    "excluded_epochs": result.artifact_result.excluded_epochs,
                    "artifact_pct": result.artifact_result.artifact_pct,
                    "method": result.artifact_result.method,
                },
                validation_summary={
                    "leading_zero_rows": result.validation.leading_zero_rows,
                },
                warnings=result.warnings,
                n_epochs=len(result.epochs),
                n_bins=len(result.bin_summary),
                source_files=[str(p) for p in paths],
                content_hash=file_content_hash,
                stage_row_counts=getattr(result, "stage_row_counts", {}) or {},
            )

            # Tier 2: warm hot cache with fresh DataFrames
            frames = CachedFrames(
                epochs=result.epochs,
                bin_summary=result.bin_summary,
                loaded_columns=set(result.epochs.columns),
                full_load=True,
            )

            with self._lock:
                self._patient_index[patient_id] = idx_entry
                self._hot_cache[patient_id] = frames
                self._hot_cache.move_to_end(patient_id)
                self._bin_summary_cache[patient_id] = result.bin_summary
                while len(self._hot_cache) > MAX_HOT_PATIENTS:
                    self._hot_cache.popitem(last=False)

            with status._lock:
                status.stage = "complete"
                status.progress = 1.0
                status.complete = True
                status.message = "Pipeline complete"
            log.info("Pipeline complete for %s (job %s)", patient_id, job_id)

            if study_name:
                self.assign_patients_to_study([patient_id], study_name)

        except Exception as e:
            log.exception("Pipeline failed for job %s", job_id)
            friendly = _user_friendly_error(e)
            with status._lock:
                status.stage = "error"
                status.error = friendly
                status.complete = True
                status.message = f"Processing failed: {friendly}"

    def run_batch(
        self,
        patients: list[dict],
    ) -> tuple[str, list[JobStatus]]:
        batch_id = str(uuid.uuid4())[:8]
        jobs = []
        for p in patients:
            config = PipelineConfig(
                artifact=ArtifactConfig(
                    mode=p.get("artifact_mode", "quality"),
                    intensity_threshold=p.get("artifact_intensity_threshold", 5.0),
                    quality_threshold=p.get("artifact_quality_threshold", 50.0),
                ),
                seizure=SeizureConfig(
                    exclusion_mode=p.get("seizure_mode", "none"),
                    probability_threshold=p.get("seizure_probability_threshold", 0.5),
                ),
                binning=BinningConfig(
                    bin_edges_hours=p.get("bin_edges_hours", [0, 6, 12, 18, 24]),
                    min_coverage_hours=p.get("min_coverage_hours", 1.0),
                ),
                rosc_time=p.get("rosc_time"),
            )
            pid = p.get("patient_id") or p["file_ids"][0]
            status = self.run_pipeline(p["file_ids"], pid, config, p.get("rosc_time"), p.get("mmx_study"), p.get("study_name"))
            jobs.append(status)
        return batch_id, jobs

    def reprocess_patient(
        self,
        patient_id: str,
        config: PipelineConfig,
        rosc_time_str: Optional[str] = None,
    ) -> JobStatus:
        """Re-run pipeline for an already-processed patient with new config.

        Looks up the original file paths from the disk cache metadata,
        then forcibly clears disk + hot cache for this patient before
        re-running so a fresh compute is guaranteed — config-hash-only
        invalidation missed stale entries whose filename prefix matched
        (same content_hash → same dir name) after a CACHE_SCHEMA_VERSION
        bump.
        """
        # Try to find original file paths from disk cache
        file_ids: list[str] | None = None

        # Check disk cache for this patient's metadata
        import json as _json
        for meta_path in sorted(self.cache_dir.glob("*/meta.json")):
            try:
                meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("patient_id") == patient_id:
                    file_ids = meta.get("source_files", [])
                    break
            except Exception:
                continue

        # Fallback: check index for source files
        if not file_ids:
            idx_meta = self._patient_index.get(patient_id)
            if idx_meta and idx_meta.source_files:
                file_ids = idx_meta.source_files

        if not file_ids:
            # Last resort: look for upload pointer files matching patient_id
            candidate = self.upload_dir / patient_id
            ptr = self.upload_dir / f"{patient_id}.ptr"
            if candidate.exists():
                file_ids = [patient_id]
            elif ptr.exists():
                file_ids = [patient_id]

        if not file_ids:
            raise FileNotFoundError(
                f"Cannot find original files for patient '{patient_id}'. "
                "Re-upload the data and run the pipeline again."
            )

        # Convert absolute paths back to file_ids the service can resolve
        resolved_ids = []
        for fpath in file_ids:
            p = Path(fpath)
            if p.is_absolute() and p.exists():
                # Create a pointer so get_upload_path can find it
                ptr_name = p.stem
                ptr_file = self.upload_dir / f"{ptr_name}.ptr"
                if not ptr_file.exists():
                    ptr_file.write_text(str(p), encoding="utf-8")
                resolved_ids.append(ptr_name)
            else:
                resolved_ids.append(fpath)

        # Force fresh compute: clear disk cache dir, hot cache, bin-summary cache,
        # and patient index entry. run_pipeline will rebuild all of these.
        from qeeg.storage.result_cache import clear_cache
        clear_cache(patient_id, self.cache_dir)
        with self._lock:
            self._hot_cache.pop(patient_id, None)
            self._bin_summary_cache.pop(patient_id, None)
            self._patient_index.pop(patient_id, None)

        study_name = self._patient_studies.get(patient_id)
        study_cfg = self._studies.get(study_name) if study_name else None
        mmx_study = study_cfg.mmx_study if study_cfg else None

        return self.run_pipeline(
            file_ids=resolved_ids,
            patient_id=patient_id,
            config=config,
            rosc_time_str=rosc_time_str,
            mmx_study=mmx_study,
            study_name=study_name,
        )

    # -- Result access --

    def list_patients(self) -> list[str]:
        """Return all known patient IDs (from index, not just hot cache)."""
        return list(self._patient_index.keys())

    def get_patient_meta(self, patient_id: str) -> Optional[PatientMeta]:
        """Tier-1 access: returns lightweight metadata. No I/O."""
        return self._patient_index.get(patient_id)

    def get_bin_summary(self, patient_id: str) -> Optional[pd.DataFrame]:
        """Load bin_summary.parquet for a patient without loading the full epochs parquet."""
        meta = self._patient_index.get(patient_id)
        if meta is None:
            return None
        # Check hot cache first
        with self._lock:
            cached = self._hot_cache.get(patient_id)
            if cached is not None and cached.bin_summary is not None:
                return cached.bin_summary
        bin_path = meta.cache_dir / "bin_summary.parquet"
        if not bin_path.exists():
            return None
        from qeeg.storage.parquet_io import load_epochs_columns
        return load_epochs_columns(bin_path)

    def get_result(self, patient_id: str) -> Optional[PatientResult]:
        """Backward-compatible: returns a PatientResult with lazily-loaded DataFrames."""
        meta = self._patient_index.get(patient_id)
        if meta is None:
            return None

        frames = self._get_or_load_frames(patient_id, meta)
        if frames is None:
            return None

        from qeeg.ingestion.parser import ParsedExport
        from qeeg.quality.artifact_filter import FilterResult
        from qeeg.validation.data_checks import ValidationReport

        art = meta.artifact_result_summary
        artifact_result = FilterResult(
            mask=pd.Series(True, index=frames.epochs.index) if frames.epochs is not None else pd.Series(dtype=bool),
            total_epochs=art.get("total_epochs", 0),
            excluded_epochs=art.get("excluded_epochs", 0),
            artifact_pct=art.get("artifact_pct", 0),
            method=art.get("method", "combined"),
        )
        val = meta.validation_summary
        validation = ValidationReport(leading_zero_rows=val.get("leading_zero_rows", 0))

        return PatientResult(
            patient_id=patient_id,
            parsed=ParsedExport(
                data=pd.DataFrame(), code_to_description={},
                description_to_codes={}, metadata={},
                code_row_index=0, trend_row_index=0,
            ),
            schema=meta.schema,
            validation=validation,
            time_info=meta.time_info,
            artifact_result=artifact_result,
            seizure_report=meta.seizure_report,
            qc=meta.qc,
            epochs=frames.epochs,
            bin_summary=frames.bin_summary,
            warnings=meta.warnings,
            stage_row_counts=meta.stage_row_counts or {},
        )

    # -- Clinical metadata --

    def store_clinical_metadata(self, metadata: list[ClinicalMetadata]) -> None:
        """Store clinical metadata for multiple patients."""
        with self._lock:
            for m in metadata:
                self._clinical_metadata[m.patient_id] = m
            log.info(f"Stored clinical metadata for {len(metadata)} patients")
            self._save_clinical_metadata()

    def get_clinical_metadata(self, patient_id: str) -> Optional[ClinicalMetadata]:
        """Retrieve clinical metadata for a patient."""
        return self._clinical_metadata.get(patient_id)

    # -- EEG date corrections --

    def store_eeg_corrections(self, corrections: list[EEGCorrection]) -> None:
        """Store EEG date corrections keyed by new_name (file stem)."""
        with self._lock:
            for c in corrections:
                self._eeg_corrections[c.new_name] = c
            log.info("Stored EEG corrections for %d files", len(corrections))
            self._save_eeg_corrections()

    def get_eeg_correction(self, new_name: str) -> Optional[EEGCorrection]:
        return self._eeg_corrections.get(new_name)

    # -- MMX configuration --

    def store_mmx_config(
        self,
        study_name: str,
        engines: dict[str, EngineConfig],
        fingerprint: str,
        source_path: str,
    ) -> None:
        """Store parsed MMX engine config for a study."""
        with self._lock:
            self._mmx_configs[study_name] = {
                "engines": engines,
                "fingerprint": fingerprint,
                "source_path": source_path,
            }
            log.info("Stored MMX config for study '%s' (%d engines)", study_name, len(engines))
            self._save_mmx_configs()

    def get_mmx_config(self, study_name: str) -> Optional[dict]:
        """Retrieve MMX config for a study. Returns dict with engines, fingerprint, source_path."""
        return self._mmx_configs.get(study_name)

    def list_mmx_configs(self) -> list[dict]:
        """List all ingested MMX configs as summaries."""
        from api.models.schemas import MmxEngineEntry
        results = []
        for study_name, cfg in self._mmx_configs.items():
            engines: dict[str, EngineConfig] = cfg["engines"]
            results.append({
                "study_name": study_name,
                "fingerprint": cfg["fingerprint"],
                "source_path": cfg.get("source_path", ""),
                "n_engines": len(engines),
                "engines": [
                    MmxEngineEntry(
                        name=ec.name,
                        epoch_duration=ec.epoch_duration,
                        epoch_step=ec.epoch_step,
                        rows_per_independent_obs=ec.rows_per_independent_obs,
                    )
                    for ec in engines.values()
                ],
            })
        return results

    def _save_mmx_configs(self) -> None:
        try:
            serializable = {}
            for study_name, cfg in self._mmx_configs.items():
                engines: dict[str, EngineConfig] = cfg["engines"]
                serializable[study_name] = {
                    "fingerprint": cfg["fingerprint"],
                    "source_path": cfg.get("source_path", ""),
                    "engines": {
                        name: {"epoch_duration": ec.epoch_duration, "epoch_step": ec.epoch_step}
                        for name, ec in engines.items()
                    },
                }
            self._mmx_configs_path.write_text(
                json.dumps(serializable, indent=2), encoding="utf-8",
            )
        except Exception as e:
            log.warning("Could not persist MMX configs: %s", e)

    # -- Studies --

    def create_study(self, name: str, mmx_study: Optional[str] = None, date_shifted: bool = False) -> StudyConfig:
        """Create or update a study."""
        import datetime
        with self._lock:
            study = StudyConfig(
                name=name,
                mmx_study=mmx_study,
                created_at=self._studies.get(name, StudyConfig(name=name)).created_at or datetime.datetime.now().isoformat(),
                date_shifted=date_shifted,
            )
            self._studies[name] = study
            self._save_studies()
            log.info("Created/updated study '%s' (mmx: %s, date_shifted: %s)", name, mmx_study, date_shifted)
        return study

    def list_studies(self) -> list[StudyConfig]:
        return list(self._studies.values())

    def get_study(self, name: str) -> Optional[StudyConfig]:
        return self._studies.get(name)

    def delete_study(self, name: str) -> int:
        """Remove a study and unassign every patient from it.

        Returns the number of patients that were unassigned. Does NOT delete
        the patients themselves. Persists both `_studies` and
        `_patient_studies` to disk.
        """
        with self._lock:
            if name not in self._studies:
                return 0
            del self._studies[name]
            all_assigned = [pid for pid, s in self._patient_studies.items() if s == name]
            for pid in all_assigned:
                self._patient_studies.pop(pid, None)
            real_unassigned = [pid for pid in all_assigned if pid in self._patient_index]
            self._save_studies()
            if all_assigned:
                self._save_patient_studies()
            log.info("Deleted study '%s' and unassigned %d real patients (%d orphans removed)", name, len(real_unassigned), len(all_assigned) - len(real_unassigned))
            return len(real_unassigned)

    def assign_patients_to_study(self, patient_ids: list[str], study_name: str) -> None:
        """Assign patients to a study."""
        with self._lock:
            for pid in patient_ids:
                self._patient_studies[pid] = study_name
            self._save_patient_studies()
            log.info("Assigned %d patients to study '%s'", len(patient_ids), study_name)

    def get_patient_study(self, patient_id: str) -> Optional[str]:
        return self._patient_studies.get(patient_id)

    def list_patients_by_study(self, study_name: str) -> list[str]:
        return [pid for pid, s in self._patient_studies.items() if s == study_name and pid in self._patient_index]

    def _sort_paths_by_corrections(self, paths: list[Path]) -> list[Path]:
        """Reorder paths using EEG corrections if available.

        Sorts by (age_in_days_at_time_of_eeg, eeg_start_time) so multi-segment
        recordings are concatenated in actual chronological order, not filename order.
        Falls back to original order for any path without a correction entry.
        """
        def sort_key(p: Path) -> tuple:
            corr = self._correction_for_path(p)
            if corr is None:
                return (99999, "99:99:99", str(p))
            return (corr.age_in_days_at_time_of_eeg, corr.eeg_start_time, str(p))

        corrected_paths = sorted(paths, key=sort_key)
        if corrected_paths != paths:
            log.info(
                "Reordered %d paths using EEG corrections: %s",
                len(paths),
                [p.stem for p in corrected_paths],
            )
        return corrected_paths

    def _correction_for_path(self, path: Path) -> Optional[EEGCorrection]:
        """Return the correction row that would be used for a CSV path.

        The embedded Persyst .dat stem is canonical; CSV stem is only a fallback.
        Keep cache-key construction, segment sorting, and timestamp correction on
        the same lookup rule so correction changes invalidate the right patients.
        """
        dat_stem = self._dat_stem_from_csv(path)
        if dat_stem and dat_stem in self._eeg_corrections:
            return self._eeg_corrections[dat_stem]
        return self._eeg_corrections.get(path.stem)

    def _relevant_corrections_for_paths(self, paths: list[Path]) -> dict[str, dict]:
        relevant: dict[str, dict] = {}
        for p in paths:
            dat_stem = self._dat_stem_from_csv(p)
            for key in (dat_stem, p.stem):
                if key and (corr := self._eeg_corrections.get(key)) is not None:
                    relevant[key] = asdict(corr)
                    break
        return relevant

    @staticmethod
    def _dat_stem_from_csv(path: Path) -> Optional[str]:
        """Read the 'File,' header line from a Persyst CSV to get the source dat stem.

        Persyst exports embed the source EEG file path in the first few header rows.
        The dat stem is the canonical key for EEG corrections — the CSV filename alone
        (often an export timestamp like '20260422_2006__') cannot be used for lookup.

        Normalizes segment suffix: '4290-10_b884347-2' → '4290-10_b884347_2'.
        """
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=encoding, newline="") as fh:
                    for i, line in enumerate(fh):
                        if i > 20:
                            break
                        low = line.lower()
                        if low.startswith("file,"):
                            dat_path = line.split(",", 1)[1].strip().strip('"')
                            stem = Path(dat_path).stem
                            # Normalize trailing dash-digit segment suffix to underscore
                            stem = re.sub(r"-(\d+)$", r"_\1", stem)
                            return stem
                break
            except (UnicodeDecodeError, OSError):
                continue
        return None

    def _apply_date_corrections(
        self, paths: list[Path], patient_id: str
    ) -> tuple[list | None, str | None]:
        """Parse files and replace de-identified ClockDateTime with synthetic timestamps.

        When EEG corrections exist for all segments AND clinical metadata provides
        the patient's age at arrest + ROSC timing, we reconstruct a synthetic timeline.

        Two modes:
        1. Full datetime (rosc_date + rosc_time or rosc_datetime):
           birthday = rosc_date − age_days
        2. Time-only (date-shifted, only rosc_time available):
           Use arbitrary epoch (2000-01-01) as birthday reference.
           The actual dates don't matter — only relative ROSC↔EEG spacing matters.

        Returns (list_of_parsed, rosc_datetime_str) or (None, None) if corrections
        don't apply.
        """
        clinical = self.get_clinical_metadata(patient_id)
        if not clinical:
            return None, None

        # Need at least rosc_time to construct a synthetic ROSC
        rosc_time_str = clinical.rosc_time
        if not rosc_time_str and clinical.effective_rosc_datetime:
            # Extract time from combined datetime
            parts = clinical.effective_rosc_datetime.split()
            rosc_time_str = parts[1] if len(parts) >= 2 else parts[0] if ":" in parts[0] else None
        if not rosc_time_str:
            return None, None

        # All paths must have corrections.
        # Look up by dat stem from CSV File header (Persyst embeds the source .dat path
        # in header row 1: "File,<path>"). Fall back to CSV stem for backwards compat.
        corrections = []
        for p in paths:
            dat_stem = self._dat_stem_from_csv(p)
            corr = self._correction_for_path(p)
            if corr is None:
                log.debug(
                    "No correction found for %s (dat_stem=%s)", p.name, dat_stem
                )
                return None, None
            corrections.append(corr)

        # Resolve engine cadence from the patient's MMX study (for orig_step fallback)
        engine_step_days: Optional[float] = None
        study_name = self._patient_studies.get(patient_id)
        if study_name:
            study = self._studies.get(study_name)
            if study and study.mmx_study:
                mmx_cfg = self._mmx_configs.get(study.mmx_study)
                if mmx_cfg:
                    engines = mmx_cfg.get("engines") or {}
                    # Use the minimum epoch_step across engines — rows are emitted
                    # at the fastest engine's cadence (typically FFT at 1s). Taking
                    # the rhythmicity engine's 322s step would scale the time axis
                    # by ~322x and make a 12h recording look like 3,696h.
                    candidate_steps = [
                        float(_ec.epoch_step)
                        for _ec in engines.values()
                        if getattr(_ec, "epoch_step", 0) > 0
                    ]
                    if candidate_steps:
                        engine_step_days = min(candidate_steps) / 86400.0

        # age_at_arrest_days is optional in ClinicalMetadata; without it we cannot
        # anchor the synthetic timeline and must bail rather than crash on
        # pd.Timedelta(days=None).
        if clinical.age_days is None:
            log.warning(
                "No age_at_arrest_days for patient %s — skipping date-correction path",
                patient_id,
            )
            return None, None

        # Construct synthetic birthday anchor
        if clinical.effective_rosc_datetime:
            rosc_dt = pd.Timestamp(clinical.effective_rosc_datetime)
            birthday = rosc_dt - pd.Timedelta(days=clinical.age_days)
        else:
            # Date-shifted: use arbitrary epoch + age to build synthetic timeline
            # The actual calendar dates are meaningless; only relative spacing matters.
            arbitrary_epoch = pd.Timestamp("2000-01-01")
            birthday = arbitrary_epoch
            # Construct synthetic ROSC datetime for alignment
            rosc_parts = _parse_clock_time(rosc_time_str)
            if rosc_parts is None:
                return None, None
            rh, rm, rs = rosc_parts
            rosc_dt = birthday + pd.Timedelta(
                days=clinical.age_days, hours=rh, minutes=rm, seconds=rs
            )
        excel_epoch = pd.Timestamp("1899-12-30")

        all_parsed = []
        for path, corr in zip(paths, corrections):
            parsed = parse_persyst_csv(path)
            df = parsed.data

            if "ClockDateTime" not in df.columns:
                return None, None

            # Synthetic start for this segment
            start_parts = _parse_clock_time(corr.eeg_start_time)
            if start_parts is None:
                return None, None
            h, m, s = start_parts
            # birthday preserves ROSC clock time (Task 4 D.4); normalize here
            # so eeg_start_time is applied as the actual clock time on that day.
            seg_start = birthday.normalize() + pd.Timedelta(
                days=corr.age_in_days_at_time_of_eeg, hours=h, minutes=m, seconds=s
            )

            # Preserve original relative epoch spacing (including within-segment gaps)
            # while replacing the de-identified absolute date/time anchor.
            n = len(df)
            clock = df["ClockDateTime"]
            if pd.api.types.is_numeric_dtype(clock):
                original_serial = pd.to_numeric(clock, errors="coerce")
            else:
                # Datetime or string — convert to Excel serial via timedelta
                ts = pd.to_datetime(clock, errors="coerce")
                original_serial = (ts - excel_epoch).dt.total_seconds() / 86400.0

            seg_start_serial = (seg_start - excel_epoch).total_seconds() / 86400.0
            # Uniform-step fallback cadence for broken/non-monotonic raw timestamps.
            # Use the segment's OWN median positive inter-row delta — the true Persyst
            # trend cadence (~1s) — rather than a coarse MMX engine step, which would
            # scale a 24h segment by hundreds of x (a 148s step inflated 4290-13 from
            # 24h to 3,553h). engine_step_days / 1s are only last-resort defaults.
            _pos_delta = original_serial.astype(float).diff()
            _pos_delta = _pos_delta[_pos_delta > 0]
            if len(_pos_delta):
                fallback_step = float(_pos_delta.median())
            else:
                fallback_step = engine_step_days if engine_step_days else 1.0 / 86400.0
            if n <= 1 or original_serial.isna().any():
                offsets = pd.Series(np.arange(n, dtype=float), index=df.index) * fallback_step
            else:
                offsets = original_serial.astype(float) - float(original_serial.iloc[0])
                if (offsets.diff().dropna() <= 0).any() or float(offsets.iloc[-1]) <= 0:
                    offsets = pd.Series(np.arange(n, dtype=float), index=df.index) * fallback_step
            df["ClockDateTime"] = seg_start_serial + offsets

            all_parsed.append(parsed)
            log.info(
                "Date-corrected %s: age=%d start=%s → synthetic %s",
                path.stem, corr.age_in_days_at_time_of_eeg,
                corr.eeg_start_time, seg_start,
            )

        return all_parsed, str(rosc_dt)

    # Prefixes for derived fft_power columns (not in schema, computed during pipeline)
    _DERIVED_FFT_PREFIXES = (
        "fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
        "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
        "theta_delta_ratio_", "alpha_delta_ratio_",
        "log_theta_delta_ratio_", "log_alpha_delta_ratio_",
    )
    # Keyed by str(epochs_path) → list of derived FFT column names (cleaned parquet names).
    # Populated on first read; avoids a separate _pq.read_schema() call on repeat requests.
    _fft_derived_cols_cache: dict[str, list[str]] = {}

    def _parquet_cols_for_families(
        self, meta: "PatientMeta", families: list[str], epochs_path: "Path",
        requested_columns: set[str] | None = None,
    ) -> list[str]:
        """Compute the minimal set of parquet column names needed for the given families.

        Parquet columns are cleaned (lowercase, sanitized). After load, parquet_io
        reverses the mapping back to original names. We compute cleaned names from
        schema codes so we can do column-pushdown before loading any row data.
        """
        import pyarrow.parquet as _pq
        from qeeg.storage.parquet_io import _clean_column_name

        needed: set[str] = {"_hours_relative", "_usable"}
        for entry in meta.schema:
            if entry.family in families and (
                requested_columns is None
                or entry.code in requested_columns
                or (entry.common_name and entry.common_name in requested_columns)
            ):
                needed.add(_clean_column_name(entry.code))

        if "fft_power" in families:
            cache_key = str(epochs_path)
            if cache_key in self._fft_derived_cols_cache:
                needed.update(self._fft_derived_cols_cache[cache_key])
            else:
                try:
                    parquet_schema = _pq.read_schema(str(epochs_path))
                    derived = [
                        c for c in parquet_schema.names
                        if any(c.startswith(p) for p in self._DERIVED_FFT_PREFIXES)
                    ]
                    self._fft_derived_cols_cache[cache_key] = derived
                    if requested_columns is None:
                        needed.update(derived)
                    else:
                        needed.update([c for c in derived if c in requested_columns])
                except Exception as exc:
                    log.warning("Could not read parquet schema for derived FFT columns %s: %s", epochs_path, exc)

        return list(needed)

    def get_epoch_data_selective(
        self, patient_id: str, families: list[str],
        requested_columns: set[str] | None = None,
    ) -> tuple[list[float], dict[str, list]]:
        """Like get_epoch_data but only loads the columns needed for `families`.

        Avoids loading the full parquet (which can be 1.5GB for wide patients)
        when the frontend only needs one or two families.
        """
        meta = self._patient_index.get(patient_id)
        if meta is None:
            return [], {}

        epochs_path = meta.cache_dir / "epochs.parquet"
        if not epochs_path.exists():
            return [], {}

        columns = self._parquet_cols_for_families(meta, families, epochs_path, requested_columns)
        frames = self._get_or_load_frames(patient_id, meta, columns=columns)
        if frames is None:
            return [], {}

        from qeeg.pipeline import PatientResult
        from qeeg.ingestion.parser import ParsedExport
        from qeeg.quality.artifact_filter import FilterResult
        from qeeg.validation.data_checks import ValidationReport

        art = meta.artifact_result_summary
        result = PatientResult(
            patient_id=patient_id,
            parsed=ParsedExport(
                data=pd.DataFrame(), code_to_description={},
                description_to_codes={}, metadata={},
                code_row_index=0, trend_row_index=0,
            ),
            schema=meta.schema,
            validation=ValidationReport(leading_zero_rows=0),
            time_info=meta.time_info,
            artifact_result=FilterResult(
                mask=pd.Series(dtype=bool),
                total_epochs=art.get("total_epochs", 0),
                excluded_epochs=art.get("excluded_epochs", 0),
                artifact_pct=art.get("artifact_pct", 0),
                method=art.get("method", "combined"),
            ),
            seizure_report=meta.seizure_report,
            qc=meta.qc,
            epochs=frames.epochs,
            bin_summary=frames.bin_summary,
            warnings=meta.warnings,
        )
        return self.get_epoch_data(result, families, requested_columns)

    def get_spectrogram_data_selective(
        self, patient_id: str, spec_type: str,
    ) -> tuple[list[float], list[float], list[list]]:
        """Like get_spectrogram_data but only loads spectrogram family columns."""
        meta = self._patient_index.get(patient_id)
        if meta is None:
            return [], [], []

        epochs_path = meta.cache_dir / "epochs.parquet"
        if not epochs_path.exists():
            return [], [], []

        family_map = {
            "fft_left":    "fft_spectrogram",
            "fft_right":   "fft_spectrogram",
            "asymmetry":   "asymmetry",
            "asymmetry_hemi": "asymmetry", "asymmetry_ant": "asymmetry",
            "asymmetry_post": "asymmetry", "asymmetry_temp": "asymmetry",
            "asymmetry_parasag": "asymmetry",
            "rhythmicity": "rhythmicity",
            "coherence":   "coherence_spectrogram",
        }
        family = family_map.get(spec_type, spec_type)
        columns = self._parquet_cols_for_families(meta, [family], epochs_path)
        frames = self._get_or_load_frames(patient_id, meta, columns=columns)
        if frames is None:
            return [], [], []

        from qeeg.pipeline import PatientResult
        from qeeg.ingestion.parser import ParsedExport
        from qeeg.quality.artifact_filter import FilterResult
        from qeeg.validation.data_checks import ValidationReport

        art = meta.artifact_result_summary
        result = PatientResult(
            patient_id=patient_id,
            parsed=ParsedExport(
                data=pd.DataFrame(), code_to_description={},
                description_to_codes={}, metadata={},
                code_row_index=0, trend_row_index=0,
            ),
            schema=meta.schema,
            validation=ValidationReport(leading_zero_rows=0),
            time_info=meta.time_info,
            artifact_result=FilterResult(
                mask=pd.Series(dtype=bool),
                total_epochs=art.get("total_epochs", 0),
                excluded_epochs=art.get("excluded_epochs", 0),
                artifact_pct=art.get("artifact_pct", 0),
                method=art.get("method", "combined"),
            ),
            seizure_report=meta.seizure_report,
            qc=meta.qc,
            epochs=frames.epochs,
            bin_summary=frames.bin_summary,
            warnings=meta.warnings,
        )
        return self.get_spectrogram_data(result, spec_type)

    def _build_code_to_name(self, schema: list) -> dict[str, str]:
        """Build I-code → common_name mapping from schema."""
        mapping = {}
        for entry in schema:
            if entry.common_name:
                mapping[entry.code] = entry.common_name
        return mapping

    def get_epoch_data(
        self, result: PatientResult, families: list[str],
        requested_columns: set[str] | None = None,
    ) -> tuple[list[float], dict[str, list]]:
        """Extract epoch data for requested column families.

        Returns columns keyed by common_name (not I-codes) for frontend readability.
        Derived columns (fft_delta_anterior, etc.) already have readable names.
        """
        df = result.epochs
        hours = df["_hours_relative"].tolist()
        usable = df["_usable"].tolist()

        code_to_name = self._build_code_to_name(result.schema)

        # Parquet columns are lowercase; schema codes may be uppercase — normalize.
        df_cols_lower = {c.lower(): c for c in df.columns}

        # Select schema columns matching requested families
        requested: list[tuple[str, str]] = []  # (df_col, output_name)
        for entry in result.schema:
            if entry.family in families:
                df_col = entry.code if entry.code in df.columns else df_cols_lower.get(entry.code.lower())
                if df_col is not None:
                    name = entry.common_name or entry.code
                    if requested_columns is None or name in requested_columns or entry.code in requested_columns:
                        requested.append((df_col, name))

        # Also include derived columns for fft_power family
        if "fft_power" in families:
            for col in df.columns:
                if col.startswith(("fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
                                   "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
                                   "theta_delta_ratio_", "alpha_delta_ratio_",
                                   "log_theta_delta_ratio_", "log_alpha_delta_ratio_")):
                    if requested_columns is None or col in requested_columns:
                        requested.append((col, col))  # already readable names

        columns: dict[str, list] = {}
        for df_col, output_name in requested:
            series = df[df_col]
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
            # Skip non-numeric columns (e.g., aEEG classification strings)
            if series.dtype == "object" or series.dtype.name == "category":
                continue
            values = series.replace({np.nan: None, np.inf: None, -np.inf: None}).tolist()
            columns[output_name] = values

        return hours, {"_usable": usable, **columns}

    def get_spectrogram_data(
        self, result: PatientResult, spec_type: str,
    ) -> tuple[list[float], list[float], list[list]]:
        """Extract spectrogram matrix for a given type (fft_spectrogram, asymmetry, rhythmicity).

        Returns (frequencies, hours, matrix) where matrix[freq_idx][time_idx].
        """
        df = result.epochs
        hours = df["_hours_relative"].tolist()
        schema = result.schema

        # Map spec_type to family name.
        # asymmetry_hemi/ant/post/temp/parasag select per-region asymmetry spectrograms.
        _ASYM_REGION_TYPES = {
            "asymmetry_hemi":    "Hemi",
            "asymmetry_ant":     "Ant",
            "asymmetry_post":    "Post",
            "asymmetry_temp":    "Temp",
            "asymmetry_parasag": "Para",
        }
        family_map = {
            "fft_left":    "fft_spectrogram",
            "fft_right":   "fft_spectrogram",
            "asymmetry":   "asymmetry",
            "rhythmicity": "rhythmicity",
            "coherence":   "coherence_spectrogram",
            **{k: "asymmetry" for k in _ASYM_REGION_TYPES},
        }
        family = family_map.get(spec_type, spec_type)

        # Find all columns for this family, sorted by sub_index
        all_family_entries = sorted(
            [e for e in schema if e.family == family],
            key=lambda e: e.sub_index,
        )

        # Filter by hemisphere if fft
        if spec_type == "fft_left":
            all_family_entries = [e for e in all_family_entries if e.hemisphere == "left"]
        elif spec_type == "fft_right":
            all_family_entries = [e for e in all_family_entries if e.hemisphere == "right"]

        if not all_family_entries:
            # fft_left/fft_right must return fully empty — never leak hours when
            # no fft_spectrogram columns exist for the requested hemisphere.
            if spec_type in ("fft_left", "fft_right"):
                return [], [], []
            return [], hours, []

        # Select the best I-group whose sub-column count matches expected n_bins.
        # This filters out scalar indices (EASI/REASI for asymmetry) and selects
        # a single electrode chain (for FFT spectrogram).
        from qeeg.constants import SPECTROGRAM_FREQ_MAP

        spec_key_map = {
            "fft_spectrogram": "fft_spectrogram",
            "asymmetry": "asymmetry_spectrogram",
            "rhythmicity": "rhythmicity_spectrogram",
            "coherence_spectrogram": "coherence_spectrogram",
        }
        spec_key = spec_key_map.get(family, "fft_spectrogram")
        spec_info = SPECTROGRAM_FREQ_MAP.get(spec_key, {})
        expected_n_bins = spec_info.get("n_bins", 40)

        # Group entries by i_group
        groups: dict[int, list] = {}
        for e in all_family_entries:
            groups.setdefault(e.i_group, []).append(e)

        # For asymmetry spec types, prefer I-groups matching the requested region keyword.
        # "asymmetry" (legacy) defaults to hemisphere.
        if family == "asymmetry":
            region_keyword = _ASYM_REGION_TYPES.get(spec_type, "Hemi")
            region_groups = {
                ig: elist for ig, elist in groups.items()
                if any(region_keyword.lower() in e.trend_name.lower() for e in elist)
            }
            if region_groups:
                groups = region_groups

        # For FFT spectrograms, prefer hemisphere-level I-groups over per-region chains
        # (anterior, posterior). Without this, best_ig can pick the wrong region when
        # multiple I-groups share the same 40-bin count.
        if family == "fft_spectrogram":
            hemi_groups = {
                ig: elist for ig, elist in groups.items()
                if any("hemisphere" in e.trend_name.lower() for e in elist)
            }
            if hemi_groups:
                groups = hemi_groups

        # Select the I-group whose count is closest to expected_n_bins
        best_ig = min(groups, key=lambda ig: abs(len(groups[ig]) - expected_n_bins))
        entries = sorted(groups[best_ig], key=lambda e: e.sub_index)

        if not entries:
            return [], hours, []

        # Hard-enforce the resolved family. For fft_left/fft_right the selected
        # I-group MUST be literally "fft_spectrogram" — never leak asymmetry or
        # fft_power columns through when the requested family is absent.
        if spec_type in ("fft_left", "fft_right") and entries[0].family != "fft_spectrogram":
            return [], [], []

        # Build frequency axis from sub_index via the canonical schema
        # (subcol_schema.get_spectrogram_bin_freq encodes the correct formula
        # per family: linear for FFT/asym/coherence, sqrt for rhythmicity).
        from qeeg.ingestion.subcol_schema import get_spectrogram_bin_freq

        # spec_type comes from the frontend (e.g. "fft_left", "asymmetry_hemi",
        # "rhythmicity"). Map it to the schema family slug used for bin freqs.
        _schema_family_for_spec_type = {
            "fft_left":            "fft_spectrogram",
            "fft_right":           "fft_spectrogram",
            # The bare "asymmetry" spec_type was missing here. Without it the
            # lookup fell through to entries[0].family -- "asymmetry", which is
            # not a schema key -- so get_spectrogram_bin_freq returned None and
            # the axis came from the (k-1)*resolution fallback: 0.00..19.50 Hz
            # instead of 0.50..20.00. Every bin was labelled half a bin low and
            # the top bin vanished off the axis.
            "asymmetry":           "asymmetry_spectrogram",
            "asymmetry_hemi":      "asymmetry_spectrogram",
            "asymmetry_ant":       "asymmetry_spectrogram",
            "asymmetry_post":      "asymmetry_spectrogram",
            "asymmetry_temp":      "asymmetry_spectrogram",
            "asymmetry_parasag":   "asymmetry_spectrogram",
            "rhythmicity":         "rhythmicity_spectrogram",
            "coherence":           "coherence_spectrogram",
        }
        schema_family = _schema_family_for_spec_type.get(spec_type, entries[0].family)

        # Fallback resolution from the legacy SPECTROGRAM_FREQ_MAP for any
        # family not yet known to the schema's freq_formula table.
        freq_min_fallback = spec_info.get("freq_min", 0.0)
        resolution_fallback = spec_info.get("resolution_hz", 0.5)

        frequencies = []
        matrix = []
        for entry in entries:
            freq = get_spectrogram_bin_freq(schema_family, entry.sub_index)
            if freq is None:
                freq = freq_min_fallback + (entry.sub_index - 1) * resolution_fallback
            frequencies.append(freq)
            if entry.code in df.columns:
                row = df[entry.code].replace({np.nan: None}).tolist()
            else:
                row = [None] * len(hours)
            matrix.append(row)

        return frequencies, hours, matrix

    def get_overlay_data(self, result: PatientResult) -> dict:
        """Compute artifact regions, bin boundaries, and gap regions."""
        df = result.epochs
        hours = df["_hours_relative"].values
        clean = df["_artifact_clean"].values

        # Find contiguous artifact regions
        artifact_regions = []
        in_artifact = False
        start_h = 0.0
        for i in range(len(clean)):
            if not clean[i] and not in_artifact:
                in_artifact = True
                start_h = hours[i]
            elif clean[i] and in_artifact:
                in_artifact = False
                artifact_regions.append({"start_hours": float(start_h), "end_hours": float(hours[i])})
        if in_artifact:
            artifact_regions.append({"start_hours": float(start_h), "end_hours": float(hours[-1])})

        # Bin boundaries from bin_summary
        bin_boundaries = []
        for _, row in result.bin_summary.iterrows():
            bin_boundaries.append(float(row["bin_start_hours"]))
        if len(result.bin_summary) > 0:
            last = result.bin_summary.iloc[-1]
            bin_boundaries.append(float(last["bin_end_hours"]))

        # Gap regions (where time jumps significantly)
        gap_regions = []
        if len(hours) > 1:
            diffs = np.diff(hours)
            median_diff = np.median(diffs)
            threshold = max(median_diff * 5, 0.5)  # 5x median or 30 min
            for i, d in enumerate(diffs):
                if d > threshold:
                    gap_regions.append({
                        "start_hours": float(hours[i]),
                        "end_hours": float(hours[i + 1]),
                    })

        return {
            "artifact_regions": artifact_regions,
            "bin_boundaries": bin_boundaries,
            "gap_regions": gap_regions,
        }

    def get_overlay_data_selective(self, patient_id: str) -> dict:
        """Like get_overlay_data but only loads _hours_relative and _artifact_clean."""
        meta = self._patient_index.get(patient_id)
        if meta is None:
            return {"artifact_regions": [], "bin_boundaries": [], "gap_regions": []}

        overlay_cols = ["_hours_relative", "_usable", "_artifact_clean"]
        frames = self._get_or_load_frames(patient_id, meta, columns=overlay_cols)
        if frames is None:
            return {"artifact_regions": [], "bin_boundaries": [], "gap_regions": []}

        from qeeg.pipeline import PatientResult
        from qeeg.ingestion.parser import ParsedExport
        from qeeg.quality.artifact_filter import FilterResult
        from qeeg.validation.data_checks import ValidationReport

        art = meta.artifact_result_summary
        result = PatientResult(
            patient_id=patient_id,
            parsed=ParsedExport(
                data=pd.DataFrame(), code_to_description={},
                description_to_codes={}, metadata={},
                code_row_index=0, trend_row_index=0,
            ),
            schema=meta.schema,
            validation=ValidationReport(leading_zero_rows=0),
            time_info=meta.time_info,
            artifact_result=FilterResult(
                mask=pd.Series(dtype=bool),
                total_epochs=art.get("total_epochs", 0),
                excluded_epochs=art.get("excluded_epochs", 0),
                artifact_pct=art.get("artifact_pct", 0),
                method=art.get("method", "combined"),
            ),
            seizure_report=meta.seizure_report,
            qc=meta.qc,
            epochs=frames.epochs,
            bin_summary=frames.bin_summary,
            warnings=meta.warnings,
        )
        return self.get_overlay_data(result)
