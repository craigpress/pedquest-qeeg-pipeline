# Pytest Test Reference -- qEEG Pipeline

Quick-reference for writing tests. Import paths, signatures, return types, and expected behaviors.

---

## 1. column_mapper.py (`qeeg.ingestion.column_mapper`)

### classify_family(trend_name: str) -> str

Matches `trend_name` against `FEATURE_FAMILIES` regex dict (checked in definition order, first match wins). Returns `"other"` if nothing matches.

Example pairs:
| trend_name | expected_family |
|---|---|
| `"Artifact Intensity Fp1"` | `"artifact_intensity"` |
| `"FFT Power, 1 - 4 Hz, Left Hemisphere"` | `"fft_power"` |
| `"FFT PowerRatio 8-13/1-4 Hz Right Anterior"` | `"fft_power_ratio"` |
| `"aEEG Upper Margin Left"` | `"aeeg"` |
| `"Seizure Probability P14"` | `"seizure_probability"` |
| `"RAV 6-14/1-20 Hz Left Anterior"` | `"alpha_variability"` (must match BEFORE fft_power_ratio) |
| `"Rhythmic delta indicator Left"` | `"rda"` (must match BEFORE rhythmicity) |
| `"Heart Rate"` | `"heart_rate"` |
| `"SomethingUnknown"` | `"other"` |

**Key ordering rules**: `alpha_variability` before `fft_power_ratio`; `fft_power_ratio` before `fft_power`; `rda` before `rhythmicity`.

### build_column_schema(code_to_description: dict[str, str]) -> list[ColumnEntry]

Input: dict like `{"I34_1": "FFT Power, 1 - 4 Hz, Left Hemisphere", ...}`.
Returns: list of `ColumnEntry` dataclass instances, sorted by `col_index`.

**ColumnEntry fields**: `col_index`, `code` (str), `i_group` (int), `sub_index` (int), `trend_name` (str), `family` (str), `frequency_band` (str, e.g. "delta"), `freq_min_hz` (Optional[float]), `freq_max_hz` (Optional[float]), `hemisphere` (str), `region` (str), `electrode` (str), `sub_column_name` (str, default ""), `common_name` (str, default "").

Codes not matching `r"^I(\d+)_(\d+)$"` are skipped.

### generate_common_name(entry: ColumnEntry) -> str

Produces a machine-readable Python/R-valid identifier. Examples:
| family | inputs | expected output pattern |
|---|---|---|
| `fft_power` | band="delta", hemi="left", region="anterior" | `"fft_delta_left_anterior"` |
| `artifact_intensity` | sub_column_name="fp1" | `"artifact_intensity_fp1"` |
| `aeeg` | hemi="left", sub="upper" | `"aeeg_left_upper"` |
| `heart_rate` | (no sub) | `"heart_rate"` |

### Helper functions
- `extract_frequency_range(trend_name)` -> `(float, float)` or `(None, None)`. Handles `"1 - 4 Hz"` and ratio patterns `"8-13/1-4 Hz"` (returns numerator only).
- `map_to_band(freq_min, freq_max)` -> band name string or `""`. Matches against `FREQUENCY_BANDS` dict.
- `get_columns_by_family(schema, family)` -> filtered list of ColumnEntry.
- `get_fft_power_columns(schema)` -> `{band: {region_label: code}}` nested dict.

---

## 2. pipeline.py (`qeeg.pipeline`)

### PatientResult dataclass

Fields: `patient_id` (str), `parsed` (ParsedExport), `schema` (list[ColumnEntry]), `validation` (ValidationReport), `time_info` (TimeAxisInfo), `artifact_result` (FilterResult), `seizure_report` (SeizureReport), `qc` (QCReport), `epochs` (pd.DataFrame), `bin_summary` (pd.DataFrame), `warnings` (list[str]).

### process_patient() signature

```python
def process_patient(
    csv_path: str | Path,
    config: PipelineConfig | None = None,
    patient_id: str | None = None,
    rosc_time_str: str | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
    parsed: ParsedExport | None = None,
) -> PatientResult
```

**Pipeline columns added to DataFrame**: `_timestamp`, `_hours_relative`, `_artifact_clean`, `_seizure_flag`, `_usable`, `_is_independent_fft`. Also adds all derived feature columns (regional FFT, ratios, etc.) and `_aeeg_class_{hemi}` columns.

10-step orchestration: parse -> timestamps -> validate -> align ROSC -> artifact filter -> seizure detection -> usable mask -> region mapping + derived features + aEEG classification -> time binning -> QC report.

### concatenate_and_process()

```python
def concatenate_and_process(
    file_paths: list[str | Path],
    config: PipelineConfig | None = None,
    patient_id: str | None = None,
    rosc_time_str: str | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> PatientResult
```

Parses multiple CSVs, concatenates DataFrames, sorts by ClockDateTime, uses first file's metadata. Delegates to `process_patient()` with the combined `parsed` object. Single file = direct passthrough.

---

## 3. time_binning.py (`qeeg.analysis.time_binning`)

### aggregate_by_bins() signature

```python
def aggregate_by_bins(
    df: pd.DataFrame,
    hours_relative: pd.Series,
    variables: list[str],
    edges: list[float],
    usable_mask: pd.Series | None = None,
    independent_mask: pd.Series | None = None,
    fft_columns: list[str] | None = None,
    min_coverage_hours: float = 1.0,
    suppression_columns: list[str] | None = None,
    suppression_threshold: float = 0.5,
    seizure_mask: pd.Series | None = None,
    epoch_duration_sec: float = 1.0,
) -> pd.DataFrame
```

**Output DataFrame columns**: `bin_label` (e.g. "0-6h"), `bin_start_hours`, `bin_end_hours`, `n_total_epochs`, `n_usable_epochs`, `n_observed`, `n_effective_fft`, `coverage_hours`, `coverage_fraction`, `meets_minimum` (bool), `background_continuity_index`, `seizure_burden_hours`, `missingness_flag`, plus per-variable: `{var}_median`, `{var}_mean`, `{var}_sd`, `{var}_p05`, `{var}_p10`, `{var}_p25`, `{var}_p75`, `{var}_p90`, `{var}_p95`, `{var}_iqr`, `{var}_min`, `{var}_max`, `{var}_n`, `{var}_trimmed_mean_20pct`, `{var}_cv`. FFT/power variables additionally get `{var}_log_mean` and `{var}_log_sd`. Trajectory columns `{var}_slope` are appended for variables with ≥2 valid bins.

Coverage = n_usable_epochs × `epoch_duration_sec` / 3600.0. Bins below `min_coverage_hours` get NaN-filled stats.

### summarize_bin()

```python
def summarize_bin(df_bin, variables, independent_mask=None, fft_columns=None) -> dict
```

Computes per variable: `median`, `mean`, `sd`, `p05`, `p10`, `p25`, `p75`, `p90`, `p95`, `iqr`, `min`, `max`, `n`, `trimmed_mean_20pct` (trims 10% from each tail = 20% total; falls back to mean when n < 4), `cv` (NaN for zero, near-zero, or negative means). Independent mask is ONLY applied to variables in the `fft_columns` set. Non-FFT variables (aeeg_, seizure_, suppression_, spike_, pd_, sleep_, heart_rate) use ALL epochs.

### Independent mask logic

`NON_FFT_PREFIXES = ("aeeg_", "seizure_", "suppression_", "spike_", "pd_", "sleep_", "heart_rate")`. Variables starting with these prefixes are NOT filtered by the independent mask.

`LOG_TRANSFORM_PREFIXES = ("fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_", "total_power_")` -- these get log-transform statistics (geometric mean, log SD).

---

## 4. seizure.py (`qeeg.analysis.seizure`)

### SeizureReport dataclass

Fields: `total_seizure_epochs` (int), `seizure_burden_pct` (float), `max_seizure_probability` (float), `seizure_events` (int), `max_hourly_burden_pct` (float), `has_status_epilepticus` (bool), `longest_seizure_minutes` (float), `time_to_first_seizure_hours` (Optional[float]), `per_bin_burden` (dict[str, float]). Has `.to_dict()` method.

### detect_seizure_columns(columns: list[str], code_to_desc: dict[str, str]) -> dict[str, str]

Returns `{role: column_code}` where role is one of:
- `"probability"` -- matches `"seizureprobability"` (spaces stripped, case-insensitive)
- `"detections"` -- matches `"seizure"` AND `"detection"` in description
- `"notifications"` -- matches `"seizure"` AND `"notification"` in description

### compute_seizure_mask()

```python
def compute_seizure_mask(
    df: pd.DataFrame,
    seizure_columns: dict[str, str],
    mode: str = "none",
    probability_threshold: float = 0.5,
) -> pd.Series  # bool, True = seizure epoch
```

Modes:
- `"none"`: all False (no seizure detection)
- `"detected"`: uses `seizure_columns["detections"]` column, True where value > 0
- `"probability"`: uses `seizure_columns["probability"]` column, True where value >= threshold

---

## 5. result_cache.py (`qeeg.storage.result_cache`)

### content_hash_file(path: Path) -> str

Streams SHA-256 in 8MB chunks. Returns hex digest string.

### content_hash_files(paths: list[Path]) -> str

Hashes multiple files sorted by name for determinism. Single combined SHA-256.

### _cache_key(content_hash: str, config_dict: dict) -> str

Combines: `__version__` + content_hash + JSON-serialized config_dict (sorted keys). Returns first 16 chars of SHA-256 of that combined string. Version changes auto-invalidate cache.

### save_result(result, config_dict, content_hash, source_files, cache_dir) -> Path

Saves to `{cache_dir}/{hash}_{patient_id}/`:
- `epochs.parquet`
- `bin_summary.parquet`
- `schema.json` (list of column entry dicts)
- `meta.json` (patient_id, cache_key, content_hash, source_files, qc dict, seizure_report dict, time_info, warnings, n_epochs, n_bins, config)

### load_result(content_hash, config_dict, cache_dir) -> dict | None

Returns `{"epochs": DataFrame, "bin_summary": DataFrame, "schema": list[dict], "meta": dict}` or `None` if cache miss/stale. Finds matching dir via `_find_by_content_hash` which compares `cache_key` in `meta.json`.

---

## 6. API Endpoints (`api/main.py` + routes)

### Health check
`GET /api/health` -> `{"status": "ok", "patients_loaded": int}`

### Upload routes (`api/routes/upload.py`)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/upload/local` | `LocalPathRequest` (body: `{paths: list[str]}`) | `list[UploadResponse]` |
| POST | `/api/upload` | multipart `files` | `list[UploadResponse]` |

`UploadResponse`: `{file_id, filename, size_bytes}`

### Pipeline routes (`api/routes/pipeline.py`)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/pipeline/run` | `PipelineRunRequest` | `PipelineRunResponse` (`{job_id, patient_id}`) |
| GET | `/api/pipeline/status/{job_id}` | -- | SSE stream |
| POST | `/api/batch/run` | `BatchRunRequest` | `BatchRunResponse` (`{batch_id, jobs}`) |
| GET | `/api/batch/status/{batch_id}` | -- | SSE stream |

`PipelineRunRequest`: `{file_ids, patient_id?, rosc_time?, artifact_mode="combined", artifact_intensity_threshold=5.0, artifact_detector_threshold=0.5, artifact_quality_threshold=50.0, seizure_mode="none", seizure_probability_threshold=0.5, bin_edges_hours=[0,6,12,18,24,48,72], min_coverage_hours=1.0}`

### Patient routes (`api/routes/patients.py`)
| Method | Path | Response Model |
|---|---|---|
| GET | `/api/patients` | `list[PatientSummary]` |
| GET | `/api/patients/{patient_id}` | `PatientSummary` |
| GET | `/api/patients/{patient_id}/schema` | `list[ColumnEntryResponse]` |
| GET | `/api/patients/{patient_id}/epochs` | `EpochDataResponse` |
| GET | `/api/patients/{patient_id}/spectrogram/{spec_type}` | `SpectrogramResponse` |
| GET | `/api/patients/{patient_id}/bins` | `BinSummaryResponse` |
| GET | `/api/patients/{patient_id}/overlay` | `OverlayDataResponse` |
| GET | `/api/compare?ids=...` | `ComparisonResponse` |

### Export routes (`api/routes/export.py`)
| Method | Path | Response |
|---|---|---|
| GET | `/api/export/{patient_id}/{fmt}` | StreamingResponse (csv, xlsx, json, parquet, wide, long, codebook) |

---

## 7. upload.py details (`api/routes/upload.py`)

### Local path endpoint (`POST /api/upload/local`)

Validates each path: must exist, must be `.csv`. Creates a `.ptr` pointer file containing the real path (not a copy). The file_id is `{uuid_hex8}_{sanitized_name}`.

### _sanitize_filename(name: str) -> str

Strips path components via `Path(name).name`, replaces non-word/non-dash/non-dot chars with `_`. Returns `"upload.csv"` if result is empty.

### Upload endpoint (`POST /api/upload`)

Streams uploaded file to disk in 1MB chunks. Max size: 5GB. Validates `.csv` extension.

---

## 8. pipeline_service.py (`api/services.pipeline_service`)

### PipelineService

Two-tier cache: in-memory OrderedDict (max 50 patients) + disk cache at `.qeeg_cache/`.

### run_pipeline(file_ids, patient_id, config, rosc_time_str) -> JobStatus

Creates a `JobStatus(job_id, patient_id)`, submits `_run_in_thread` to ThreadPoolExecutor (2 workers). Returns the status immediately.

### .ptr file mechanism

`get_upload_path(file_id)` checks: (1) direct file at `upload_dir/file_id`, (2) pointer file at `upload_dir/{file_id}.ptr` containing the real path. Returns the resolved real path if pointer exists and target is valid.

### _run_in_thread flow

1. Hash file contents
2. Check disk cache (`load_result`)
3. If cache hit: reconstruct PatientResult from cached data
4. If cache miss: call `process_patient()` or `concatenate_and_process()`
5. Save to disk cache (`save_result`)
6. Store in memory OrderedDict

---

## 9. artifact_filter.py (`qeeg.quality.artifact_filter`)

### FilterResult dataclass

Fields: `mask` (pd.Series, True=keep), `total_epochs` (int), `excluded_epochs` (int), `artifact_pct` (float), `method` (str).

### apply_artifact_filter()

```python
def apply_artifact_filter(
    df: pd.DataFrame,
    artifact_columns: dict[str, list[str]],  # keys: 'intensity', 'detector', 'quality'
    mode: str = "combined",
    intensity_threshold: float = 0.5,
    detector_threshold: float = 0.5,
    quality_threshold: float = 50.0,
    min_clean_electrodes: int = 10,
) -> FilterResult
```

Modes:
- `"none"`: all True mask, 0% artifact
- `"intensity"`: exclude where max intensity across columns >= threshold
- `"detector"`: exclude where >50% of detector columns exceed threshold
- `"quality"`: exclude where fewer than `min_clean_electrodes` have quality <= threshold/100
- `"combined"`: all three ANDed together

Quality note: Persyst quality is a degradation metric (low = good). Threshold is divided by 100 for comparison.

---

## 10. time_axis.py (`qeeg.alignment.time_axis`)

### TimeAxisInfo dataclass

Fields: `reference` (str: `"rosc"` or `"recording_start"`), `reference_time` (pd.Timestamp), `column_name` (str, default `"hours_relative"`).

### build_time_axis(timestamps: pd.Series, rosc_time: pd.Timestamp | None) -> tuple[pd.Series, TimeAxisInfo]

If `rosc_time` is provided: hours = (timestamps - rosc_time) in hours, reference="rosc".
Otherwise: hours = (timestamps - first_timestamp) in hours, reference="recording_start".

Returns `(hours_series, TimeAxisInfo)`.

---

## 11. derived_features.py (`qeeg.features.derived_features`)

### compute_all_derived(df: pd.DataFrame, region: str) -> pd.DataFrame

Expects columns: `fft_delta_{region}`, `fft_theta_{region}`, `fft_alpha_{region}`, `fft_beta_{region}`.

Creates columns:
- `total_power_{region}` = delta + theta + alpha + beta
- `rel_delta_{region}` = delta / total (NaN where total=0)
- `rel_theta_{region}`, `rel_alpha_{region}`, `rel_beta_{region}` (same pattern)
- `theta_delta_ratio_{region}` = theta / delta (NaN where delta=0)
- `alpha_delta_ratio_{region}` = alpha / delta
- `log_theta_delta_ratio_{region}` = log10(theta/delta), clipped to 1e-6
- `log_alpha_delta_ratio_{region}` = log10(alpha/delta), clipped to 1e-6

Returns empty DataFrame if any input column is missing.

### get_independent_mask(df, fft_columns, interval=8) -> pd.Series

`FFT_UPDATE_INTERVAL = 8` (from constants).

Logic: compares each row to previous row across all fft_columns. A row is "independent" (True) if:
1. It's the first row (always True), OR
2. Any FFT column value changed from previous row (NaN-aware: NaN->NaN is NOT a transition), OR
3. Fallback: no transition detected within `interval` rows, force True

---

## 12. aeeg_classification.py (`qeeg.features.aeeg_classification`)

### classify_aeeg_series(upper, lower, pct_bs=None) -> pd.Series (categorical)

Per-epoch classification using `classify_aeeg_epoch(upper, lower, pct_bs)`.

Categories (checked top to bottom -- order matters):
- **FT** (Flat Trace): upper < 5 uV AND lower < 5 uV
- **CLV** (Continuous Low Voltage): upper < 10 uV
- **BS** (Burst-Suppression): lower < 5 uV, upper > 25 uV (implied), pct_bs > 50%
- **DNV** (Discontinuous Normal Voltage): lower < 5 uV, upper > 10 uV
- **CNV** (Continuous Normal Voltage): both margins adequate (fallback)

`AEEG_CLASSES = ["FT", "CLV", "BS", "DNV", "CNV"]` -- severity ordering worst to best.

NaN inputs -> "unknown".

---

## 13. data_checks.py (`qeeg.validation.data_checks`)

### ValidationReport dataclass

Fields: `total_rows` (int), `leading_zero_rows` (int), `timestamp_gaps` (list[dict] with keys `start_idx`, `end_idx`, `gap_seconds`), `out_of_range` (dict[str, int]), `phi_detected` (bool), `warnings` (list[str]).

Property: `is_valid` -> True if no warnings or all warnings contain "warning" (case-insensitive).

### validate_export(df, timestamps, fft_columns, column_families, metadata=None) -> ValidationReport

Runs:
1. `detect_leading_zeros(df, fft_columns)` -- checks first 50 rows for all-zero FFT
2. `detect_timestamp_gaps(timestamps, threshold_seconds=60.0)` -- gaps > 60s
3. `check_value_ranges(df, column_families)` -- physiological ranges: fft_power 0-500, fft_power_ratio 0-100, electrode_quality 0-100, seizure_probability 0-1, artifact_intensity 0-100, aeeg 0-500
4. PHI detection: if patient_name exists and isn't all X's, sets `phi_detected=True` and strips it

---

## 14. pyproject.toml

```toml
version = "0.2.0"
name = "qeeg-pipeline"
requires-python = ">=3.11"

dependencies = [
    "pandas>=2.0",
    "numpy>=1.24",
    "pydantic>=2.0",
    "pyarrow>=12.0",
    "plotly>=5.15",
    "streamlit>=1.30",
    "scipy>=1.10",
    "openpyxl>=3.1",
]

[project.scripts]
qeeg = "qeeg.cli:main"
```

Build system: setuptools >= 68.0. Packages: `qeeg*`, `pages*`.

---

## Key Constants (qeeg/constants.py)

- `FFT_UPDATE_INTERVAL = 8` (seconds between independent FFT observations)
- `FEATURE_FAMILIES`: OrderedDict of 25 family patterns (regex). Order-dependent matching.
- `FREQUENCY_BANDS`: standard EEG bands (delta, theta, alpha, beta, gamma)
- `SPECTROGRAM_FREQ_MAP`: freq_min, resolution_hz, n_bins per spectrogram type
- `MIN_BIN_COVERAGE_HOURS = 1.0`
