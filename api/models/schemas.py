"""Pydantic response models for the qEEG API."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Optional


class UploadResponse(BaseModel):
    file_id: str
    patient_id: str
    filename: str
    size_bytes: int


class PipelineRunRequest(BaseModel):
    file_ids: list[str]
    patient_id: Optional[str] = None
    rosc_time: Optional[str] = None
    artifact_mode: str = "quality"
    artifact_intensity_threshold: float = 5.0
    artifact_quality_threshold: float = 50.0
    seizure_mode: str = "none"
    seizure_probability_threshold: float = 0.5
    bin_edges_hours: list[float] = Field(default=[0, 6, 12, 18, 24, 48, 72])
    min_coverage_hours: float = 1.0
    mmx_study: Optional[str] = None
    study_name: Optional[str] = None


class PipelineRunResponse(BaseModel):
    job_id: str
    patient_id: str


class PipelineProgress(BaseModel):
    job_id: str
    stage: str
    progress: float
    message: str = ""
    patient_id: str = ""
    complete: bool = False
    error: Optional[str] = None


class BatchRunRequest(BaseModel):
    patients: list[PipelineRunRequest]


class BatchRunResponse(BaseModel):
    batch_id: str
    jobs: list[PipelineRunResponse]


class ColumnEntryResponse(BaseModel):
    col_index: int
    code: str
    i_group: int
    sub_index: int
    trend_name: str
    family: str
    frequency_band: str
    freq_min_hz: Optional[float]
    freq_max_hz: Optional[float]
    hemisphere: str
    region: str
    electrode: str
    sub_column_name: str
    common_name: str


class QCSummary(BaseModel):
    total_epochs: int
    usable_epochs: int
    artifact_pct: float
    seizure_epochs: int
    seizure_pct: float
    recording_duration_hours: float
    usable_hours: float
    median_suppression_pct: float | None = None
    bin_coverage: dict[str, float]
    warnings: list[str]


class SeizureSummary(BaseModel):
    total_seizure_epochs: int
    seizure_burden_pct: float
    max_seizure_probability: float
    seizure_events: int
    max_hourly_burden_pct: float = 0.0
    # ``has_status_epilepticus`` is deprecated — the name falsely implies an
    # ILAE clinical diagnosis. Clients should prefer
    # ``status_epilepticus_screen_flag``; both fields carry the same value for
    # one release.
    has_status_epilepticus: bool = False
    status_epilepticus_screen_flag: bool = False
    longest_seizure_minutes: float = 0.0
    time_to_first_seizure_hours: Optional[float] = None
    per_bin_burden: dict[str, float] = {}


class TimeAxisResponse(BaseModel):
    reference: str
    reference_time: str
    rosc_date: Optional[str] = None
    rosc_time: Optional[str] = None
    eeg_start_date: Optional[str] = None
    eeg_start_time: Optional[str] = None
    date_shifted: bool = False
    age_at_arrest_days: Optional[int] = None
    age_at_eeg_start_days: Optional[int] = None
    hours_rosc_to_eeg: Optional[float] = None


class PatientSummary(BaseModel):
    patient_id: str
    qc: QCSummary
    seizure: SeizureSummary
    time_axis: TimeAxisResponse
    n_columns: int
    n_epochs: int
    families: list[str]
    study_name: Optional[str] = None


class EpochDataResponse(BaseModel):
    """Columnar format for efficient chart rendering."""
    hours: list[float]
    usable: list[bool]
    columns: dict[str, list[Optional[float]]]


class SpectrogramResponse(BaseModel):
    frequencies: list[float]
    hours: list[float]
    matrix: list[list[Optional[float]]]
    colorscale: str = "hot"


class BinRow(BaseModel):
    bin_label: str
    bin_start_hours: float
    bin_end_hours: float
    coverage_hours: float
    coverage_fraction: float = 0.0
    n_observed: int = 0
    n_effective_fft: int = 0
    meets_minimum: bool
    background_continuity_index: Optional[float] = None
    seizure_burden_hours: Optional[float] = None
    missingness_flag: str = ""
    metrics: dict[str, Optional[float]]


class BinSummaryResponse(BaseModel):
    bins: list[BinRow]
    bin_edges: list[float]


class ArtifactRegion(BaseModel):
    start_hours: float
    end_hours: float


class OverlayDataResponse(BaseModel):
    artifact_regions: list[ArtifactRegion]
    bin_boundaries: list[float]
    gap_regions: list[ArtifactRegion]


class ComparisonMetric(BaseModel):
    patient_id: str
    metric_name: str
    value: Optional[float]
    bin_label: str = ""


class ComparisonResponse(BaseModel):
    patient_ids: list[str]
    metrics: list[ComparisonMetric]


class ChartPanelMetadata(BaseModel):
    """Metadata describing a single dashboard chart panel."""
    panel_id: str
    display_name: str
    description: str
    source_families: list[str]
    variables: list[str]
    units: str
    derivation: str
    cadence_seconds: int
    window_seconds: float
    filtering: str


class ChartMetadataResponse(BaseModel):
    panels: list[ChartPanelMetadata]


class ReprocessRequest(BaseModel):
    """Settings for reprocessing a patient with updated config."""
    artifact_mode: str = "quality"
    artifact_intensity_threshold: float = 5.0
    artifact_quality_threshold: float = 50.0
    seizure_mode: str = "none"
    seizure_probability_threshold: float = 0.5
    bin_edges_hours: list[float] = Field(default=[0, 6, 12, 18, 24, 48, 72])
    min_coverage_hours: float = 1.0


# ---------------------------------------------------------------------------
# Folder scan models (S4)
# ---------------------------------------------------------------------------

FileType = Literal[
    "persyst_csv", "clinical_csv", "corrections_csv", "raw_eeg", "unknown"
]


class ScannedFile(BaseModel):
    path: str
    filename: str
    file_type: FileType
    size_bytes: int
    error: Optional[str] = None
    csv_panel_type: Optional[str] = None  # set for persyst_csv files


class ScanRequest(BaseModel):
    folder_path: str
    recursive: bool = True


class ScanResponse(BaseModel):
    folder: str
    files: list[ScannedFile]
    counts: dict[str, int]


# ---------------------------------------------------------------------------
# Manifest builder models (S4)
# ---------------------------------------------------------------------------


class PatientManifestEntry(BaseModel):
    patient_id: str
    persyst_files: list[str]
    clinical_csv: Optional[str] = None
    corrections_csv: Optional[str] = None
    raw_eeg_files: list[str] = []
    total_duration_hours: float
    total_epochs: int
    n_columns_per_file: list[int]
    file_panel_types: list[str] = []  # parallel to persyst_files
    validation_errors: list[str]
    validation_warnings: list[str]
    requires_corrections: bool


class ManifestBuildRequest(BaseModel):
    scanned_files: list[ScannedFile]


class ManifestBuildResponse(BaseModel):
    patients: list[PatientManifestEntry]
    total_patients: int
    global_clinical_csv: Optional[str] = None
    global_corrections_csv: Optional[str] = None
    validation_summary: dict[str, int]


# ---------------------------------------------------------------------------
# MMX configuration models (S7)
# ---------------------------------------------------------------------------


class MmxEngineEntry(BaseModel):
    name: str
    epoch_duration: float
    epoch_step: float
    rows_per_independent_obs: int


class MmxUploadRequest(BaseModel):
    path: str
    study_name: str


class MmxUploadResponse(BaseModel):
    study_name: str
    fingerprint: str
    engines: list[MmxEngineEntry]


class MmxConfigSummary(BaseModel):
    study_name: str
    fingerprint: str
    source_path: str
    n_engines: int
    engines: list[MmxEngineEntry]


# ---------------------------------------------------------------------------
# Study management models
# ---------------------------------------------------------------------------


class StudyResponse(BaseModel):
    name: str
    mmx_study: str | None = None
    created_at: str | None = None
    patient_count: int = 0
    date_shifted: bool = False


class CreateStudyRequest(BaseModel):
    name: str
    mmx_study: str | None = None
    date_shifted: bool = False
