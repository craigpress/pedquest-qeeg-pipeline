---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/design
---

# PedQuEST qEEG Analysis Pipeline — Architecture Reference

**Repository:** [github.com/craigpress/qeeg-analysis-pipeline](https://github.com/craigpress/qeeg-analysis-pipeline)
**Working tree:** `c:/Users/craig/claude/qEEG projects/qEEG analysis pipeline`
**Active branch (this snapshot):** `feat/workbench-v2`
**Last refreshed:** 2026-04-24

> Single-document reference for the framework, codebase, key concepts, and operational
> patterns. Designed to be pasted into a prompt so a fresh model can work the codebase
> without reading source files first. Where this doc and the code disagree, **the code
> wins** — verify before assuming.

---

## 1. What this is and who it's for

A research-grade quantitative-EEG (qEEG) feature-extraction + visualization pipeline for
**pediatric post-cardiac-arrest neurocritical care**. Built by Craig Press (pediatric
neurologist, MD/PhD) to support the [PedQuEST](https://www.pedquest.org/) and POCCA
studies at the University of Michigan. Inputs are **Persyst EEG Trends CSV exports**
(plus optional MMX panel configs, clinical metadata, and date corrections); outputs are
binned features, an interactive workbench, and research-ready datasets for R / Python /
Stata analysis.

Clinical primitives the pipeline produces:

- Seizure probability + detections (P14)
- Band power (delta / theta / alpha / beta) and rel-band ratios
- ADR (alpha-delta ratio) and TDR (theta-delta ratio) — neurological-recovery indicators
- aEEG envelopes (max/min/p50/p75/p25 percentiles; no classification ribbon — Hellström-Westas is neonatal-only, not applied in PedQuEST/POCCA)
- Suppression ratio (BSR), spectral edge frequency
- Asymmetry (REASI / EASI), coherence, rhythmicity spectrograms
- Spike density (left / right / generalized)
- Artifact intensity / electrode quality / artifact-detector flags
- Coverage + missingness flags per time bin

---

## 2. Tech stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11+ (3.13 recommended). FastAPI + uvicorn (ASGI), pandas, NumPy, PyArrow / DuckDB for parquet, Pydantic v2 for models. |
| Storage | Parquet on disk, JSON sidecars for metadata, content-fingerprint cache directory at `.qeeg_cache/`. |
| Frontend | React 18 + TypeScript, Vite, Zustand for state, Recharts for line/area, custom canvas for spectrograms, BaseUI primitives + Tailwind, shadcn-style components. |
| Tests | pytest (~398 tests), Playwright pytest plugin (live UI smoke tests, opt-in). |
| Dev launcher | `python start.py --dev` (FastAPI on :8000 + Vite on :3000). |

---

## 3. Top-level layout

```
qEEG analysis pipeline/
├── qeeg/                          # Pure-Python processing library
│   ├── __version__.py
│   ├── config.py                  # PipelineConfig (artifact / seizure / binning / time)
│   ├── constants.py
│   ├── pipeline.py                # process_patient + concatenate_and_process
│   ├── ingestion/                 # CSV → DataFrame + schema
│   ├── analysis/                  # time_binning + seizure burden
│   ├── features/                  # region_mapping + derived_features
│   ├── alignment/                 # ROSC time axis, subject registry
│   ├── quality/                   # artifact_filter, qc_report
│   ├── validation/                # alignment_check, data_checks
│   └── storage/                   # parquet_io, export, result_cache, project_store
│
├── api/                           # FastAPI HTTP layer
│   ├── main.py                    # app factory + router wiring + static mount
│   ├── routes/                    # one file per resource (patients/pipeline/export/scan/studies/upload/manifest)
│   └── services/
│       └── pipeline_service.py    # orchestration: jobs, hot cache, reprocess, lazy load
│
├── frontend/                      # Vite + React workbench
│   └── src/
│       ├── App.tsx, main.tsx
│       ├── api/                   # fetch wrappers, typed
│       ├── stores/appStore.ts     # Zustand: patient, config, cursor, time domain
│       ├── hooks/                 # usePatientData, useChartMetadata, useTimeSync, useCursorSnapshot, …
│       ├── panels/                # manifest + columnResolver (declarative panel/instrument graph)
│       ├── components/
│       │   ├── workbench/         # IconRail, KpiStrip, PanelSwitcher, TimeAxis, Inspector, EventList
│       │   ├── panels/            # PersystPanel + renderers/
│       │   ├── charts/            # legacy chart components (some archived)
│       │   ├── import/            # ImportView, ManifestReview
│       │   └── ui/                # primitives
│       └── types/api.ts           # mirrors Pydantic response models
│
├── tests/                         # pytest, ~398 tests
├── docs/                          # this directory
│   ├── ARCHITECTURE.md            # ← THIS FILE
│   ├── PANEL_REFERENCE.md         # per-panel/per-trace breakdown
│   ├── handoffs/                  # session handoffs (chronological)
│   ├── diagnostics/               # one-off bug investigations
│   ├── validation/                # validation runs vs reference data
│   └── dev/                       # platform-specific dev notes
│
├── Ref Files/                     # Persyst MMX configs, panel specs, .chm
├── test_data/                     # synthetic + stress-fixture patients
├── .qeeg_cache/                   # processed-patient cache (gitignored)
├── start.py                       # combined dev launcher
├── README.md                      # user-facing install + features
└── HANDOFF.md                     # legacy session handoff (older)
```

---

## 4. Core data flow

### 4.0 Upstream Persyst workflow and source-of-truth rule

The source EEG is acquired first, then processed by Persyst using an **MMX file**.
The MMX defines the panels, instruments, trend calculations, channels, frequency
bands, and engine cadence. Persyst then exports one or more panel-specific CSVs.

For this pipeline, **the MMX is the reference for column and statistic semantics**.
The CSVs contain the exported numeric data from real EEGs, but their raw I-code column
names are not stable across different panel exports or MMX configurations. Never infer
cross-panel or cross-segment identity from raw CSV column names alone when an MMX is
available.

**Source-of-truth MMX:** `Ref Files/PedQuEST_Pennsieve_V10_research.mmx` — the only
template this release supports. It is parsed and serialized to
`docs/persyst_v10_catalog.json` (regen via `scripts/sync_persyst_docs.py`); a
human-readable summary lives at `docs/PERSYST_V10_REFERENCE.md` and the per-panel
breakdown at `docs/persyst_v10_panel_index.md`. It defines **22 panels, 10 engines,
370 unique instruments, 962 panel-slot references**, including non-lateralized
`Anterior`/`Posterior` channel sets (regional power/ratios/aEEG/BSR/PeakEnvelope/SEF),
**relative band power** (`FFT PowerRatio {band}/1-30 Hz` → `rel_{band}_{location}`),
distinct ADR/TDR slugs, and Persyst-native **Status Epilepticus** and **Seizure
Burden** metrics (`status_epilepticus_persyst_*`, `seizure_burden_persyst_*`) kept
distinct from — not replacing — the pipeline-calculated screen flag / burden.
Persyst-native regional/relative values take precedence over the pipeline-computed
aggregates (compute steps skip columns already present), **except** the ESE/burden
metrics which coexist with the calculated ones. Earlier templates are archived under
`_archive/` and are not readable by this release.

### 4.1 Inputs

1. **Persyst Trends CSV** (one or more files per patient).
   Format: ~60-row preamble with metadata + a row of `I{group}_{sub}` codes + a "trend
   name" row above it; data starts immediately after the code row.
2. **MMX panel config** (optional, `.mmx` XML). Source of truth for which Persyst
   instrument produced each I-code, and for trend definition/cadence. Per-study.
3. **Clinical metadata CSV** (optional). Maps patient → birthday / age at ROSC / arrest
   datetime. Persists to `.qeeg_cache/clinical_metadata.json`.
4. **EEG corrections CSV** (optional). Maps de-identified Persyst dat-stems → real age
   at recording start + clock time. Persists to `.qeeg_cache/eeg_corrections.json`.
5. **Study config** (`StudyConfig`). Per-study MMX + cohort.

### 4.2 Pipeline stages — `qeeg/pipeline.py`

`process_patient(csv_path, config, …)` runs these in order:

1. **Parse** — `parse_persyst_csv` walks the preamble, finds the code row, reads the
   data with pandas, converts `ClockDateTime` from Excel serial. Writes a sidecar
   describing the column layout + parquet readiness for the DuckDB fast path.
2. **Schema** — resolve I-codes to typed `ColumnEntry` (family, hemisphere, region,
   frequency band, units, common_name slug). MMX-first when MMX is provided
   (`build_column_schema_with_mmx`); otherwise regex-only (`build_column_schema`).
3. **Timestamps** — coerce to `pd.Timestamp[ns]`; build hours-relative axis.
4. **Validate** — `validate_export` checks ranges, sentinel values, leading-zero rows.
5. **ROSC alignment** — `parse_rosc_time` + `check_rosc_alignment` produce a
   ROSC-relative `hours_relative` series and a `time_info` block. Trims pre-ROSC epochs
   when EEG started early.
6. **Artifact filter** — `apply_artifact_filter` builds a usability mask per epoch from
   one of `intensity / detector / quality / combined / none` modes.
7. **Seizure** — detect seizure epochs (P14 probability + detector), compute burden
   relative to artifact-clean denominator.
8. **Region mapping + derived features** — bilateral aggregates, ADR/TDR, log-ratios.
9. **Independent observation count** — uses MMX engine cadences when available so
   independent-N reflects true sampling, not 1Hz over-sampling. Human-readable
   engine/window/cadence/effective-N rules are documented in
   [`TREND_ENGINE_REFERENCE.md`](TREND_ENGINE_REFERENCE.md).
10. **Time binning** — `bin_epochs` reduces epochs → `bin_summary` per
    `bin_edges_hours`. Coverage + missingness flags.
11. **QC report** — `build_qc_report` summarizes the run.
12. **Cache write** — `save_result` persists `epochs.parquet`, `bin_summary.parquet`,
    `schema.json`, `meta.json` under `.qeeg_cache/{content_hash[:12]}_{patient_id}/`.

### 4.3 Multi-segment patients — `qeeg/ingestion/segment_merge.py`

Many patients ship as several CSVs (continuation recordings, or different MMX panel
configs of the same `.dat`). Naive concat is dangerous because the same `I288_1` code
may resolve to different instruments per segment.

`merge_segments_by_semantic_name(parsed_exports, mmx=None)`:

1. Build per-segment `ColumnEntry` schema (MMX-first when `mmx` provided).
2. Rename each segment's columns from raw I-codes to **`common_name` slugs** (e.g.
   `fft_delta_anterior`). Reserved-derived slugs (those produced downstream by
   `compute_regional_features` / `compute_all_derived`) get a `_asym` suffix when they
   collide with bilateral aggregates.
3. Build a master `ClockDateTime` index (sorted union across all segments).
4. For each slug, gather contributions across segments and merge by **rank-ordered
   fill** — highest non-NaN density wins; first-seen segment is the tiebreak. Remaining
   NaN cells are back-filled from lower-ranked contributors.
5. Emit a single `ParsedExport` whose columns are slugs (no raw I-codes) + a pre-built
   schema aligned to the slugs.

This replaced an earlier raw-I-code recoding path that silently produced 83.5% NaN tails
on patient `4290-1`. Cache schema bumped to **v3** at the changeover.

### 4.4 Cache architecture — `qeeg/storage/result_cache.py` + `api/services/pipeline_service.py`

Three-tier:

1. **Disk cache** (`.qeeg_cache/{content_hash[:12]}_{patient_id}/`) — content-fingerprint
   addressed. Keyed by:
   `__version__ | v{CACHE_SCHEMA_VERSION} | content_hash | config | clinical | corrections | mmx`
   any change to algorithms or upstream metadata triggers a fresh compute.
2. **Patient index** (in-memory dict) — lightweight `PatientMeta` for every cached
   patient, loaded from `meta.json` + `schema.json` on startup. No size limit.
3. **Hot cache** (LRU `OrderedDict`) — recently-accessed `CachedFrames` with epochs
   DataFrame + bin summary. Bounded to `MAX_HOT_PATIENTS`. Lazy-loaded from parquet
   with column-selective reads.

**Content fingerprint:** `name | size | mtime | head4KB | tail4KB`. Stat-only is
collision-prone for `cp -p` / `rsync -a`-preserved mtimes; full streaming SHA-256 was
30+ minutes on 4GB network-share CSVs. The 4KB head + tail sample catches the common
collision modes at near-zero cost.

**Reprocess flow** (`POST /api/pipeline/reprocess/{patient_id}`):
1. Look up source files from cached `meta.json`.
2. `clear_cache(patient_id)` — removes the disk cache dir + hot/index entries for that patient.
3. Re-run `run_pipeline(file_ids=…)` with new config.

`CACHE_SCHEMA_VERSION` is the nuclear option — bump it to invalidate every cached
patient on next access (used after algorithm changes that break old results).

### 4.5 ROSC alignment + date corrections

De-identified Persyst exports often have date-shifted `ClockDateTime`. Two-input
reconstruction in `_apply_date_corrections` (`api/services/pipeline_service.py`):

- **Clinical metadata** gives `birthday` (derived from `rosc_datetime - age_days`).
- **EEG corrections** give per-segment `(age_days, eeg_start_time)`.

Then `seg_start = birthday + correction.age_days + correction.eeg_start_time`
synthesizes a real timeline. `birthday` is normalized at the point of use only
(midnight) so ROSC clock time is preserved when not normalizing.

The frontend renders the timeline as `0h (ROSC) → roscOffset + recording_duration`,
where `roscOffset = max(0, time_axis.hours_rosc_to_eeg)`. Anywhere a fraction of the
total span is computed (cursor jump targets, time-axis ticks) **must** use this same
denominator — `frontend/src/components/workbench/TimeAxis.tsx` is the canonical pattern.

---

## 5. Backend module guide

### `qeeg/ingestion/`

| File | Purpose |
|---|---|
| `parser.py` | `parse_persyst_csv(path) → ParsedExport`. Header walk, code-row detection, encoding detection, sidecar read/write, DuckDB fast-path on cached parquet. |
| `column_mapper.py` | `ColumnEntry`, `build_column_schema`, `build_column_schema_with_mmx`. Resolves I-codes to typed metadata. |
| `mmx_parser.py` | Reads Persyst `.mmx` XML → engine + instrument index. |
| `segment_merge.py` | Multi-segment semantic-name merge (see §4.3). |
| `quick_scan.py` | First-32KB classifier — panel type, patient ID, encoding — used for fast folder scans. |
| `patient_grouper.py` | Groups files by patient_id during folder scan. |
| `cadence.py` | MMX engine cadence resolution (epoch step, etc.). |
| `timestamps.py` | Excel-serial → `pd.Timestamp` conversion. |
| `sidecar.py` | Per-CSV JSON sidecar with parsed metadata + parquet status. |
| `parquet_convert.py` | Background CSV → parquet conversion (one-shot or queued). |
| `conversion_queue.py` | Throttled queue for parquet conversions. |
| `duckdb_reader.py` | Fast load of parquet via DuckDB when sidecar marks a CSV as ready. |
| `spectrogram_parser.py` | Spectrogram-family parsing (rhythmicity / FFT / asymmetry / coherence). |

### `qeeg/analysis/` and `qeeg/features/`

| File | Purpose |
|---|---|
| `analysis/time_binning.py` | `bin_epochs` — reduces epochs into time bins; coverage + missingness flags. |
| `analysis/seizure.py` | `compute_seizure_mask`, `compute_seizure_report`, burden math. |
| `features/region_mapping.py` | `compute_regional_features` — bilateral / anterior / posterior aggregates. |
| `features/derived_features.py` | `compute_all_derived` — ADR / TDR / log-ratios. |

### `qeeg/alignment/` and `qeeg/quality/`

| File | Purpose |
|---|---|
| `alignment/time_axis.py` | `parse_rosc_time`, `check_rosc_alignment`, `build_time_axis`. |
| `alignment/subject_registry.py` | Patient identity reconciliation across sources. |
| `quality/artifact_filter.py` | `apply_artifact_filter` — modes: intensity / detector / quality / combined / none. Returns mask + per-mode diagnostic. |
| `quality/qc_report.py` | `build_qc_report`, summary stats. |

### `qeeg/storage/`

| File | Purpose |
|---|---|
| `result_cache.py` | Content-fingerprint hashing, `_cache_key`, `save_result`, `load_result`, `clear_cache`. `CACHE_SCHEMA_VERSION = 3`. |
| `parquet_io.py` | Type-preserving parquet read/write, `_clean_column_name` (rstrip not strip). |
| `export.py` | 8 export formats — CSV (wide/long/semi-long/bins), Parquet, Excel, JSON, research package ZIP. |
| `project_store.py` | Cross-patient project state. |

### `qeeg/validation/`

| File | Purpose |
|---|---|
| `alignment_check.py` | Pre-run sanity (timestamps monotonic, segments overlap, etc.). |
| `data_checks.py` | Per-family value-range validation against Persyst-published scales. |

### `api/services/pipeline_service.py`

The orchestration brain. Key methods:

| Method | What it does |
|---|---|
| `run_pipeline(file_ids, patient_id, config, …)` | Schedules a job, runs `concatenate_and_process` (or `process_patient`), persists to disk + index. |
| `reprocess_patient(patient_id, config)` | Looks up source files, force-clears cache, re-runs. |
| `get_patient(patient_id)` → `PatientSummary` | Lightweight metadata for cards / list. |
| `_get_or_load_frames(patient_id, meta, columns=None)` | Two-tier lazy load. On partial-cache hit + `columns=None`, force a full reload. On partial hit + specific columns, union missing columns. |
| `_apply_date_corrections(parsed, segment_index, ...)` | Synthesizes timestamps from clinical + corrections. |
| `_dat_stem_from_csv(path)` | Reads the `File:` row to find the .dat stem (used for corrections lookup — different from `metadata.patient_id`). |

---

## 6. API surface

All endpoints under `/api`. Returns are typed via Pydantic response models in
`api/models/`; the frontend mirrors them in `frontend/src/types/api.ts`.

| Method + Path | Purpose |
|---|---|
| `GET /api/health` | Liveness; returns `{status, patients_loaded}`. |
| `GET /api/patients` | List loaded patients. Optional `?study=…`. |
| `GET /api/patients/{id}` | Single-patient `PatientSummary`. |
| `DELETE /api/patients/{id}` | Forget patient (removes index + disk cache). |
| `GET /api/patients/{id}/schema` | List of `ColumnEntry` for the patient. |
| `GET /api/patients/{id}/chart-metadata` | Per-instrument metadata for the workbench. |
| `GET /api/patients/{id}/epochs?columns=…` | Column-selective epoch data (lazy-loaded). |
| `GET /api/patients/{id}/spectrogram/{spec_type}` | Spectrogram bundle (rhythmicity / fft_left / fft_right / asymmetry_*). |
| `GET /api/patients/{id}/bins` | Bin-summary table. |
| `GET /api/patients/{id}/overlay?columns=…` | Compact overlay payload (artifact regions, bin boundaries, gap regions). |
| `GET /api/compare?patient_ids=…` | Cross-patient comparison rows. |
| `POST /api/pipeline/run` | Start a pipeline job; returns `{job_id, patient_id}`. |
| `GET /api/pipeline/status/{job_id}` | Job progress (stage / fraction / errors). |
| `POST /api/pipeline/reprocess/{patient_id}` | Force-reprocess with new config. |
| `POST /api/batch/run` + `GET /api/batch/status/{batch_id}` | Multi-patient batch orchestration. |
| `POST /api/scan/folder` + `/scan/folder/stream` | Recursive folder scan (SSE for stream). |
| `GET /api/scan/conversion/status` | Background CSV→parquet queue status. |
| `POST /api/manifest/build` | Manifest from a scan result. |
| `GET/POST/DELETE /api/studies` | Study CRUD + patient assignment. |
| `POST /api/upload/local` | Register CSVs from local paths (no upload — pointer files). |
| `POST /api/upload/eeg-corrections` | Upload date-correction CSV. |
| `POST /api/upload/clinical` | Upload clinical-metadata CSV. |
| `POST /api/upload/mmx` | Register an MMX file. |
| `GET /api/mmx/configs` | List known MMX configs. |
| `GET /api/export/{patient_id}/{fmt}` | Single-patient export (csv / parquet / xlsx / json / etc). |
| `POST /api/export/{patient_id}/package` | Per-patient research package (ZIP). |
| `POST /api/export/batch-package` + `/batch-semi-long` + `/cohort` | Cohort-level exports. |

---

## 7. Frontend architecture

### 7.1 Workbench shell

`frontend/src/components/workbench/WorkbenchShell.tsx` composes the v2 UI:

| Component | Role |
|---|---|
| `IconRail.tsx` | Left rail — navigates Import / Patients / Dashboard / Export. |
| `KpiStrip.tsx` | Top row of summary KPIs (duration, usable, artifact, seizure, suppression). |
| `PanelSwitcher.tsx` | Tabs across the panel manifest. |
| `TimeAxis.tsx` | Sticky time ruler (ROSC-relative). **Canonical denominator pattern** for fractional positions. |
| `Inspector.tsx` | Right rail — Cursor / Events / Params tabs; settings live here. |
| `EventList.tsx` | Seizure summary; "jump to first seizure" reuses the TimeAxis denominator. |
| `RecordingHeader.tsx` | Patient ID + duration + source. |

### 7.2 State — `frontend/src/stores/appStore.ts`

Zustand store. Notable slices:

- `patientId`, `patientSummary`
- `config` (artifactMode, artifactThreshold, seizureMode, seizureThreshold, binEdges,
  roscTime, minCoverageHours)
- `cursorPct`, `cursorValues` — cursor position + per-instrument labels
- `overlayData`, `chartMetadata`, `timeDomain`

`setPatient(id, summary)` clears overlayData / chartMetadata / timeDomain / cursorPct /
cursorValues so a new patient never inherits stale UI state.

### 7.3 Data hooks — `frontend/src/hooks/`

| Hook | Behavior |
|---|---|
| `usePatientData` | Fetches `epochs` per family. Aborts in-flight requests on patient switch / family change. |
| `useChartMetadata` | Per-instrument metadata (units, cadence, source). |
| `useCursorSnapshot` | Resolves cursor X to per-instrument Y values. |
| `useTimeSync` | Cross-panel cursor + time-domain sync. |
| `usePreRecordingGap` | Computes hatched-region between 0h (ROSC) and EEG start. |
| `useSpectrogramBundle` | Bundles spectrogram fetches per panel. |
| `usePipelineStatus` | Polls `/pipeline/status/{job_id}`. |

### 7.4 Panels — declarative manifest

`frontend/src/panels/manifest.ts` is the source of truth for which trends each panel
shows. Each panel has rows; each row has either an instrument key (resolved via
`columnResolver.ts`) or a derivation function (in `derivations.ts`). `instruments.ts`
defines per-row render configs (height, color, log scale, overlap, tooltip formatter).
The `manifest.validate.ts` test asserts column-resolution coverage.

`PersystPanel.tsx` + `SubChart.tsx` + `panels/renderers/*` consume the manifest and
render with Recharts (line / area / boolean strip / aEEG band) or canvas (spectrogram).

### 7.5 Visual conventions

- **Color key:** Blue = Left, Red = Right, Purple = L+R overlap, Green =
  Generalized / EMG / Alpha, Violet = Delta, Cyan = Theta, Amber = Beta / left spike,
  Magenta = right spike.
- **Panel sizing:** line charts ≥100–150px (60–90px is too small per Craig's
  feedback); boolean strips at 28px are intentional.
- **Recharts log axes:** tuple-range Areas silently drop their fill on log axes — use
  stacked-Area on linear scale (`AeegEnvelopeGroup` enforces `scale="auto"`). See
  `feedback_recharts_log_area.md` in auto-memory.
- **CSS color tokens:** values are full `oklch(...)` — never wrap them in `hsl(...)`.
- **Spectrograms:** server-side downsampled to 2000 points (peak-preserving). Frontend
  may also downsample but server is authoritative.

---

## 8. Key concepts (cheat sheet)

| Concept | Where it lives | Why it matters |
|---|---|---|
| **I-code** | `I{group}_{sub}` per Persyst column | Raw column label; **NOT portable** between segments — same code can mean different instruments. Never compare across segments. |
| **Common-name slug** | `column_mapper.generate_common_name` → `fft_delta_anterior` etc. | Portable semantic identity. Multi-segment merge keys on these. |
| **Reserved derived slug** | `_RESERVED_DERIVED_SLUGS` in `segment_merge.py` | Slugs produced downstream; raw trends that collide get `_asym` suffix to prevent duplicate-named columns. |
| **MMX engine + instrument** | `qeeg/ingestion/mmx_parser.py` | Authoritative source of family/region/cadence resolution. Always pass `mmx=…` when available. |
| **Cadence / `epoch_step`** | `qeeg/ingestion/cadence.py` | Defines independent observations for stats; multi-engine MMX → take MIN across engines. |
| **CACHE_SCHEMA_VERSION** | `result_cache.py:26` | Bump → all cached patients invalidate on next access. Version-pinned in cache_key. |
| **Content fingerprint** | `result_cache.py:_file_fingerprint` | name+size+mtime + 4KB head + 4KB tail. |
| **`PatientMeta` / `CachedFrames` / `JobStatus`** | `pipeline_service.py` | The three persistent in-memory shapes. |
| **`PipelineConfig`** | `qeeg/config.py` | `artifact / seizure / binning / time` sub-configs. Pydantic v2. |
| **`ParsedExport`** | `qeeg/ingestion/parser.py` | DataFrame + code↔description maps + metadata, post-parse. |
| **`PatientResult`** | `qeeg/pipeline.py` | The output of `process_patient`. |
| **`PatientSummary`** | `api/models/` + `frontend/src/types/api.ts` | Lightweight per-patient metadata sent to the workbench. |
| **`StudyConfig`** | `pipeline_service.py` | Per-study MMX + cohort. |
| **EEG correction** | `pipeline_service.py:_apply_date_corrections` | dat-stem → (age_days, eeg_start_time). Drives synthetic timestamps. |

---

## 9. Configuration surface

### Backend `PipelineConfig` (in `qeeg/config.py`)

```python
ArtifactConfig:
    mode: "none" | "intensity" | "detector" | "quality" | "combined" = "quality"
    intensity_threshold: float                 # Persyst 0–30+ scale, typical 5–15
    detector_threshold: float                  # 0–1
    quality_threshold: float                   # 0–100 (% degradation, low = good)
    min_clean_electrodes: int

SeizureConfig:
    exclusion_mode: "none" | "detected" | "probability" = "none"
    probability_threshold: float = 0.5

BinningConfig:
    bin_edges_hours: list[float] = [0, 6, 12, 18, 24, 48, 72]
    min_coverage_hours: float = 1.0

TimeConfig:
    rosc_time: str = ""                        # ISO datetime or "" = no anchor

PipelineConfig:
    artifact: ArtifactConfig
    seizure: SeizureConfig
    binning: BinningConfig
    time: TimeConfig
```

### Frontend `appStore.config`

Mirrors the backend shape but flattened with simpler keys (`artifactMode`,
`artifactThreshold`, …). `Inspector.tsx` is the only UI that toggles `artifactMode`,
and it always co-writes a sensible `artifactThreshold` default for the new mode (so
threshold scales never cross-pollute).

### Default artifact mode

`"quality"` — electrode-contact only. `"combined"` was demoted because 60Hz line
contamination caused Artifact Intensity to falsely flag ~86% of epochs.

### Research-readiness review status

The comprehensive review dated 2026-04-24 is tracked in
`docs/_archive/RESEARCH_READINESS_REVIEW_2026-04-24.md`.
That document is the current source for ship-blocking scientific/statistical risks,
audit requirements, and validation gaps. The calculation reference and fact-check plan
live in [`docs/STATISTICAL_METHODS_AND_AUDIT.md`](STATISTICAL_METHODS_AND_AUDIT.md).

### Publication-facing documentation

- [`ONBOARDING_PI.md`](ONBOARDING_PI.md) — one-page intro for PI / statistician collaborators.
- [`DATA_DICTIONARY_v4.md`](DATA_DICTIONARY_v4.md) — committed human-readable dictionary snapshot.
- [`STATISTICAL_ANALYSIS_PLAN_TEMPLATE.md`](STATISTICAL_ANALYSIS_PLAN_TEMPLATE.md) — SAP shell.
- [`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md) — cohort-lock procedure.
- [`STATISTICAL_REVIEWER_CHECKLIST.md`](STATISTICAL_REVIEWER_CHECKLIST.md) — pre-submission review checklist.
- `docs/_archive/MIGRATION_feat-workbench-v2-to-master.md` — migration notes for the master merge.

---

## 10. Common operations

### Start the dev server

```powershell
python start.py --dev --port 8000
# FastAPI on :8000 with --reload (Watchfiles), Vite on :3000
# Open http://localhost:3000
```

Pre-flight (Windows): kill stale python+node, **delete `frontend/dist/`** (otherwise
the FastAPI static mount shadows the Vite proxy and serves stale JS). The
`dev-server` skill automates both.

### Run tests

```bash
python -m pytest --ignore=tests/test_stress_gui.py -q                 # full suite, ~28s, 398 tests
python -m pytest tests/test_semantic_merge.py -x                       # focused regression set
```

### Reprocess a single patient

```bash
curl -X POST http://localhost:8000/api/pipeline/reprocess/{patient_id} \
     -H "Content-Type: application/json" -d '{}'
# Force-clears disk + hot cache, re-runs pipeline. Verify by mtime on:
#   .qeeg_cache/{hash[:12]}_{patient_id}/meta.json
```

> The `meta.json` does NOT contain a `schema_version` field (handoff doc bug). The
> v3-schema marker lives inside `cache_key`; check that, not a `schema_version` key.

### Force-invalidate every cached patient

```python
# in qeeg/storage/result_cache.py
CACHE_SCHEMA_VERSION = 4   # bump it; next access reprocesses everything
```

### Add a new study

```bash
curl -X POST http://localhost:8000/api/studies \
     -H "Content-Type: application/json" \
     -d '{"name": "POCCA", "mmx_path": "Ref Files/POCCA_Pennsieve_V5_research.mmx"}'
```

### Folder scan + import (UI)

Workbench → Import tab → Scan Folder → study selector at the top → select
multi-segment patients → Process All. Manifest review shows per-patient grouping.

### Generate stress-test data

```bash
python tests/generate_stress_data.py
# Creates 5 synthetic PedQuEST patients × 48h in test_data/stress_test/
```

---

## 11. Known gotchas (must-read before changing things)

| Gotcha | Source / why |
|---|---|
| **`_clean_column_name` must `.rstrip("_")`, not `.strip("_")`** | Pipeline-derived columns (`_hours_relative`, `_usable`) start with `_` and must keep their leading underscore through parquet round-trip. |
| **CSS color tokens are `oklch()`, never wrap in `hsl(var(--…))`** | Tokens are already complete oklch values; double-wrapping breaks color rendering. |
| **BaseUI slider `onValueChange` returns a number, NOT an array** | Always `Array.isArray(val) ? val[0] : val`. |
| **Don't kill python on Windows mid-pipeline** | Force-kill while parquet writes are in flight corrupts the cache + leaves zombie ports. Use the `dev-server` skill. |
| **Watchfiles reload is unreliable on Windows** | Documented upstream uvicorn bug. Manual restart via `dev-server` skill is the workaround. |
| **`frontend/dist/` shadows Vite in dev** | FastAPI catches all unknown routes via the static mount; if `dist/` exists in dev mode you'll see stale prod JS. |
| **Multi-segment patients can have identical `ClockDateTime`** | At sub-1s `epoch_step`, adjacent rows can share timestamps. `_indexed` drops duplicates with a logged warning during semantic merge. |
| **EEG corrections key on dat-stem, not patient ID** | `_dat_stem_from_csv` reads the `File:` row. Patient ID prefix-match would leak corrections across `4290-1` vs `4290-10`. |
| **Recharts log-axis tuple-range Area silently drops fill** | Use stacked-Area on linear scale instead. `AeegEnvelopeGroup.tsx` is the canonical workaround. |
| **Don't pin numpy<2.0 on Windows** | Installed locked DLLs cause OSError. Use minimum bounds only. |
| **Spectrogram time-axis is server-side downsampled to 2000 points** | Frontend re-downsampling is allowed but server is authoritative; bumping caps requires both sides. |
| **Persyst panel exports of the same .dat are intentional** | Craig keeps multiple Persyst exports per patient during pipeline-variant testing. Semantic merge dedupes; surface "N redundant segments" if you want UX feedback. |

---

## 12. Where to find what (quick reference)

| If you need… | Look at |
|---|---|
| Pipeline orchestration | [api/services/pipeline_service.py](../api/services/pipeline_service.py) |
| Pipeline stages | [qeeg/pipeline.py](../qeeg/pipeline.py) `process_patient` |
| Multi-segment merge | [qeeg/ingestion/segment_merge.py](../qeeg/ingestion/segment_merge.py) |
| Cache layout / schema version | [qeeg/storage/result_cache.py](../qeeg/storage/result_cache.py) |
| Persyst CSV parser | [qeeg/ingestion/parser.py](../qeeg/ingestion/parser.py) |
| MMX parser | [qeeg/ingestion/mmx_parser.py](../qeeg/ingestion/mmx_parser.py) |
| Column → semantic-name mapping | [qeeg/ingestion/column_mapper.py](../qeeg/ingestion/column_mapper.py) |
| Time / ROSC alignment | [qeeg/alignment/time_axis.py](../qeeg/alignment/time_axis.py) |
| Artifact filter | [qeeg/quality/artifact_filter.py](../qeeg/quality/artifact_filter.py) |
| Date corrections | [api/services/pipeline_service.py](../api/services/pipeline_service.py) `_apply_date_corrections`, `_dat_stem_from_csv` |
| API routes | [api/routes/](../api/routes/) one file per resource |
| Pipeline config defaults | [qeeg/config.py](../qeeg/config.py) |
| Frontend store | [frontend/src/stores/appStore.ts](../frontend/src/stores/appStore.ts) |
| Workbench shell | [frontend/src/components/workbench/WorkbenchShell.tsx](../frontend/src/components/workbench/WorkbenchShell.tsx) |
| Panel manifest | [frontend/src/panels/manifest.ts](../frontend/src/panels/manifest.ts) |
| Per-row instrument config | [frontend/src/panels/instruments.ts](../frontend/src/panels/instruments.ts) |
| Per-panel chart breakdown | [docs/PANEL_REFERENCE.md](PANEL_REFERENCE.md) |
| Persyst instrument & panel notes | [Vault: Projects/qEEG Analysis Pipeline/Persyst Reference/_index.md](file:///E:/Craig_Vault/Projects/qEEG Analysis Pipeline/Persyst Reference/_index.md) |
| Latest session handoff | `docs/_project/handoffs/` (chronological, newest = most relevant) |
| Validation reports | `docs/_project/validation/` |
| Diagnostic deep-dives | `docs/_project/diagnostics/` |

---

## 13. Recent architectural shifts (2026-04-23 → 2026-04-24)

These are the most recent invariants — read before assuming older patterns still apply:

- **Multi-segment merge is now semantic** (not raw-I-code recoding). Never re-introduce
  `_recode_colliding_igroups` or its kin — the silent collision fixer was a no-op for
  uppercase Persyst codes.
- **`CACHE_SCHEMA_VERSION = 3`** since semantic-merge landed.
- **Reprocess endpoint force-clears disk + hot cache** before re-running. Don't add
  cache-coherence shims downstream; the explicit `clear_cache(...)` is the contract.
- **Workbench v2 (icon rail / KPI strip / panel switcher / time axis / inspector)**
  replaces the old dashboard. Older `dashboard/` components are archived; use
  `workbench/`.
- **Per-family chip spinners** (Task 2 Option A). Real perf fix (Option C: per-family
  parquet split) is documented in `docs/handoffs/TASK2-dashboard-load-UX.md` but not
  implemented — it pays back on every dashboard cold-load (15-45s → 1-5s).
- **Content fingerprint mixes head + tail bytes** so `cp -p` / `rsync -a` copies don't
  collide on the cache. Stat-only hashing was the previous behavior.
- **`_get_or_load_frames`** correctly handles partial-cache + `columns=None` (force
  full reload, don't promote partial DataFrame to `full_load=True`).

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **PedQuEST** | Pediatric qEEG-driven prognostication study. |
| **POCCA** | Pediatric Outcome after Cardiac Arrest. |
| **ROSC** | Return of spontaneous circulation. T-zero on the qEEG timeline. |
| **MMX** | Persyst's panel/instrument config XML. Authoritative for I-code → instrument resolution. |
| **Persyst** | Commercial qEEG software; produces the Trends CSVs we ingest. |
| **Trends CSV** | Time-series export from Persyst with one row per epoch. |
| **Epoch** | Smallest analysis unit (typically 1s, sometimes 322s for rhythmicity). |
| **Bin** | Time aggregation window (default 6h). |
| **aEEG** | Amplitude-integrated EEG (long-window envelope). |
| **BSR** | Burst suppression ratio. |
| **ADR / TDR** | Alpha-delta / theta-delta ratios. |
| **REASI / EASI** | Rhythmic / Envelope Asymmetry Indices. |
| **Hot cache** | The bounded LRU of recently-accessed `CachedFrames`. |
| **Disk cache** | `.qeeg_cache/` content-addressed store. |
| **Patient index** | In-memory dict of `PatientMeta` for every cached patient. |
| **Sidecar** | Per-CSV JSON describing parse metadata + parquet readiness. |
| **Slug** | The lowercase-snake `common_name` semantic identifier (e.g. `fft_delta_anterior`). |

---

*Maintained alongside the code. If you change architecture, update this doc in the same
PR. The next session starts here.*
