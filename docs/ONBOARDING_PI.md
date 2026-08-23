---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# PedQuEST qEEG Pipeline — PI / Statistician Onboarding

**What it is.** A research-grade qEEG feature-extraction pipeline for
pediatric post-cardiac-arrest neurocritical care (PedQuEST, POCCA). It
ingests Persyst Trends CSV exports, aligns them to ROSC (return of
spontaneous circulation), and produces publication-ready per-patient and
per-cohort datasets for R / Python / Stata analysis.

**What you get out.**

- `epochs.parquet` — per-epoch (typically 1 s) feature values after
  artifact filtering and ROSC alignment.
- `bin_summary.parquet` — per-bin (default 6-hour) summary statistics:
  median, mean, SD, percentiles, IQR, 20% trimmed mean, CV, log mean/SD
  (positive values), coverage, missingness flag, seizure burden, BCI.
- `data_dictionary.csv/json` — definitions for every column, including
  Persyst engine, analysis window, cadence, effective-N basis.
- `provenance.json` + `audit_bundle.json` — SHA-256 hashes of raw inputs,
  MMX, clinical metadata, corrections; git commit; dependency digest;
  stage row-count checkpoints.
- `qc_report.json` — usable / artifact / seizure / suppression summary.
- A research package ZIP containing all of the above.

**Core primitives the pipeline computes.**

| Domain | Output |
|---|---|
| Seizure | P14 probability, detection events, burden (%), status-epilepticus screen |
| Spectral power | FFT delta/theta/alpha/beta per hemisphere + bilateral anterior/posterior |
| Ratios | ADR (alpha/delta), TDR (theta/delta), log-ratios, relative power |
| Background | Suppression ratio (BSR), background continuity index (BCI), aEEG envelopes |
| Asymmetry | REASI, EASI, asymmetry spectrogram (hemi / anterior / posterior / temporal / parasagittal) |
| Spikes | Left / right / generalized spike density |
| Quality | Artifact intensity, detector, electrode quality, per-bin coverage/missingness |

**Time axis.** ROSC-relative by default (`hours_relative = 0` at ROSC). If
no ROSC timestamp is supplied, falls back to recording start — the
provenance record states which.

**Artifact policy.** Default `artifact_mode = "quality"` (electrode-contact
based). Every bin-level statistic is computed over artifact-clean epochs
unless explicitly documented otherwise. Seizure epochs are optionally
excluded from non-seizure qEEG summaries (`SeizureConfig.exclusion_mode`).

**Units and cadence.** Every feature has a documented Persyst engine, MMX
EpochDuration (analysis window), EpochStep (update cadence), and
effective-N basis. See [`TREND_ENGINE_REFERENCE.md`](TREND_ENGINE_REFERENCE.md)
and [`DATA_DICTIONARY_v4.md`](DATA_DICTIONARY_v4.md).

**Publication fact-check.** See
[`STATISTICAL_METHODS_AND_AUDIT.md`](STATISTICAL_METHODS_AND_AUDIT.md) for
the independent-recompute procedure, and
[`STATISTICAL_REVIEWER_CHECKLIST.md`](STATISTICAL_REVIEWER_CHECKLIST.md)
for the pre-submission checklist.

**Freezing a cohort for analysis.** See
[`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md).

**All exported variables are exposures, not outcomes.** PedQuEST/POCCA
treat every qEEG biomarker as an exposure variable; no qEEG output is a
pre-specified primary outcome of the pipeline itself. Outcome modeling
happens downstream (R/Stata/Python) against clinical outcome variables
held outside this codebase. The pipeline's job is to produce a clean,
auditable exposure dataset.

**Core caveats to communicate in the methods section.**

- **Seizure outputs are Persyst-algorithmic (P14), not adjudicated.**
  PedQuEST/POCCA decision: no clinical adjudication. The exposures are
  the algorithmic seizure outputs as Persyst computes them. Methods
  section must say so explicitly. Use `seizure_burden_pct` and
  `seizure_events_artifact_clean` for publication tables; these reflect
  the artifact-clean denominator. Status-epilepticus is exported as
  `status_epilepticus_screen_flag` — algorithmic screen, not ILAE
  diagnosis.
- **Bilateral aggregates require both hemispheres by default**
  (`require_bilateral=True` in `qeeg/features/region_mapping.py`).
  Unilateral-only epochs return NaN. The
  `fft_{band}_{region}_sides_contributing` companion column always
  reports 0/1/2 per epoch; rows where it is 1 are excluded from the
  aggregate. Set `require_bilateral=False` for diagnostic exploration
  only.
- **Two distinct coverage fields**, both 0–1:
  - **`clean_fraction_of_observed`** = *proportion clean* (of recorded EEG).
  - **`clean_fraction_of_expected`** = *proportion of bin* (of configured bin width).
  - `coverage_fraction` is a **DEPRECATED** alias of
    `clean_fraction_of_observed`; do not use in publications.
- **Pre-specified sensitivity analysis: seizure exclusion.** Every
  feature analysis runs once with `SeizureConfig.exclusion_mode="none"`
  (seizures retained) and once with
  `SeizureConfig.exclusion_mode="probability"` or `"detected"` (seizures
  excluded from non-seizure summaries). No other sensitivity analyses
  are pre-specified.
- **Patient-level slopes** are OLS of bin midpoint vs. median, broadcast
  to every bin row — treat as a patient-level scalar, not a
  time-varying feature in mixed models.

**Patient identifiers.** `patient_id` is the study ID (PedQuEST/POCCA
de-identified study-issued identifier). Not PHI-derived. Same ID across
all exports for joins.

**Freeze trigger.** A cohort is frozen for analysis when the study MMX
file is finalized. See [`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md).
The MMX hash captured in `audit_bundle.json` is the canonical lock key.

**Where to start.** Open [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
technical tour; then run one frozen patient end-to-end against the
recompute script (`scripts/audit_recompute.py`) to confirm environment
parity before any analysis.
