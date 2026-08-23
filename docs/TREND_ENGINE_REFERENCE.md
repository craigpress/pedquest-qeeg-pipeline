---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# Trend Engine, Window, Cadence, and Effective-N Reference

Purpose: provide a reviewer-facing reference for how each Persyst trend family is
connected to its MMX calculation engine, analysis window, update cadence, and
statistical denominator. The MMX remains the source of truth. Values below are the
PedQuEST defaults used when no MMX engine metadata is available; when an MMX is
loaded, `qeeg.ingestion.cadence.get_family_cadence()` and
`get_engine_window()` use the parsed MMX `EpochStep` and `EpochDuration`.

## Terms

| Term | Meaning |
|---|---|
| CSV row | One exported Persyst trend sample after parsing and ROSC alignment. Many exports are 1 row/second, but the timestamp axis is authoritative. |
| Analysis window | MMX `EpochDuration`: the EEG duration used by the Persyst engine to compute one trend value. |
| Engine cadence | MMX `EpochStep`: how often the engine updates a trend value. |
| `n_observed` | Count of non-null usable rows for a feature in a time bin. |
| `n_effective` | Count of non-null usable rows after applying the feature's cadence/independence rule. |
| `n_effective_basis` | Export label explaining whether `n_effective` is row count or engine-cadence adjusted. |
| `n_effective_fft` | Legacy bin-level FFT-family effective count retained for backward compatibility. Prefer per-feature `n_effective` and `n_effective_basis`. |

## Effective-N Rule

For each feature in each bin:

1. Build the feature's usable rows from `_usable` and non-null feature values.
2. Determine the feature family from the MMX-aware schema.
3. Resolve the family to its producing Persyst engine.
4. If the engine `EpochStep` is greater than the CSV row cadence, count only cadence-independent rows for `n_effective`.
5. If the engine updates every row, `n_effective = n_observed` and `n_effective_basis = "row_count"`.
6. If the pipeline cannot reconstruct the engine-specific independence rule during audit, the audit script reports the field as `not checked` rather than substituting row count.

The intent is to avoid overstating statistical sample size when a trend is repeated,
held constant, or generated from a slower Persyst engine than the CSV row spacing.

## Trend Family Reference

| Trend family | Main examples | Persyst engine | Window seconds | Step seconds | Effective-N basis |
|---|---|---:|---:|---:|---|
| `fft_power` | Delta/theta/alpha/beta band power, regional band summaries | `FFTEngine01` | 4.0 | 8 | `fft_power_cadence_adjusted` |
| `fft_power_ratio` | Persyst FFT power ratios (unrecognized denominator) | `FFTEngine01` | 4.0 | 8 | `fft_power_ratio_cadence_adjusted` |
| `adr` | Band-vs-delta ratios: ADR (8-13/1-4), TDR (4-8/1-4) | `FFTEngine01` | 4.0 | 8 | `adr_cadence_adjusted` |
| `relative_power` | Relative band power: band / total 1-30 Hz | `FFTEngine01` | 4.0 | 8 | `relative_power_cadence_adjusted` |
| `alpha_variability` | Alpha variability/RAV style FFT-derived features | `FFTEngine01` | 4.0 | 8 | `alpha_variability_cadence_adjusted` |
| `fft_spectrogram` | Left/right FFT spectrogram frequency bins | `FFTEngine01` | 4.0 | 8 | `fft_spectrogram_cadence_adjusted` |
| `spectral_edge` | SEF50/SEF90 style spectral edge trends | `FFTEngine01` | 4.0 | 8 | `spectral_edge_cadence_adjusted` |
| `asymmetry` | EASI/REASI and asymmetry spectrograms | `FFTEngine01` | 4.0 | 8 | `asymmetry_cadence_adjusted` |
| `suppression_ratio` | BSR left/right/all-10-20 suppression trends | `Amplitude01` | 10.0 | 10 | `suppression_ratio_cadence_adjusted` |
| `rhythmicity` | Rhythmicity spectrogram (sqrt-scaled bin axis `f_k = (1 + (k-1)/24)²`; bin 49 = 9 Hz) and rhythmicity trend features. Column slugs use 2-decimal center-frequency with `_` for the decimal point (`9_00hz`), not range. | `RhythmicityEngine01` | 3.0 | 2 | `rhythmicity_cadence_adjusted` |
| `rda` | Rhythmic delta activity style features | `RhythmicityEngine01` | 3.0 | 2 | `rda_cadence_adjusted` |
| `rhythmic_delta` | Boolean rhythmic-delta flags (LAD+/LPD+/LRD+/RAD+/RPD+/RRD+) — thresholds on the Rhythmicity Spectrogram delta band, **not** ACNS periodic discharges | `RhythmicityEngine01` | 3.0 | 2 | `rhythmic_delta_cadence_adjusted` |
| `artifact_intensity` | Artifact intensity by channel/region | `Artifact01` | 1.2 | 1 | `row_count` |
| `electrode_quality` | Electrode quality/contact trends | `Artifact01` | 1.2 | 1 | `row_count` |
| `aeeg` | aEEG envelope percentiles: max, min, p50, p75, p25 (statistical percentiles per CSV ref §3.4 — NOT Persyst bandwidth/percent-burst-suppression/amplitude) | `aEEG01` | 1.0 | 1 | `row_count` |
| `peak_envelope` | Peak envelope trends | `PeakEnvelope01` | 1.0 | 1 | `row_count` |
| `seizure_probability` | P14 seizure probability | `SeizureProbabilityP1401` | 1.0 | 1 | `row_count` |
| `seizure_detection` | Binary seizure detection trend | `SeizureProbabilityP1401` | 1.0 | 1 | `row_count` |
| `seizure_notification` | Seizure notification/event trend | `SeizureProbabilityP1401` | 1.0 | 1 | `row_count` |
| `spike_density` | Left/right/generalized spike density | `SpikeDensityV101` | 1.0 | 1 | `row_count` |

## Non-Analysis Families

Some Persyst trend families exist in the column mapper (`qeeg/ingestion/column_mapper.py::FEATURE_FAMILIES`) but are not produced by a dedicated analysis engine with its own EpochDuration/EpochStep. These are mapped to the default 1-second cadence when resolving `get_family_cadence()` and are not independently sampled features.

| Family | Nature | Default handling |
|---|---|---|
| `heart_rate` | EKG-derived beats-per-minute label | 1 s nominal cadence; not part of the scientific feature set. Treated as a display-only metadata row. |
| `annotation` | Clinician/system annotations (Comments) | No cadence; textual. Excluded from statistical summaries. |
| `time_display` | Clock-time display row | No cadence; timestamp. Excluded from statistical summaries. |
| `coherence_spectrogram` | Coherence spectrogram (Persyst Coherence panel) | 1 s default until an engine cadence is confirmed from the MMX; prefer MMX-derived cadence when present. |
| `sleep` | Sleep staging trend | 1 s default; not used in PedQuEST/POCCA analyses. |

These families are **not** in `FAMILY_ENGINE_MAP`. If a publication analysis depends on any of them, add an explicit engine/cadence row here and in `qeeg/ingestion/cadence.py` first.

## Derived Features

Derived features inherit the effective-N interpretation of their source engine:

| Derived family | Source | Effective-N interpretation |
|---|---|---|
| `total_power_*` | Sum of FFT delta/theta/alpha/beta power | FFT cadence-adjusted. |
| `rel_delta_*`, `rel_theta_*`, `rel_alpha_*`, `rel_beta_*` | FFT band / total FFT power | FFT cadence-adjusted. |
| `theta_delta_ratio_*`, `alpha_delta_ratio_*` | FFT band ratios | FFT cadence-adjusted. |
| `log_theta_delta_ratio_*`, `log_alpha_delta_ratio_*` | Log FFT band ratios | FFT cadence-adjusted. |
| Bilateral anterior/posterior FFT summaries | Left/right regional FFT power | FFT cadence-adjusted; side contribution counts document whether one or two hemispheres contributed. |

## How To Fact-Check

For a publication audit:

1. Confirm `provenance.json` records the MMX file hash and MMX engine summary.
2. Confirm `data_dictionary.csv` or `data_dictionary.json` includes `cadence_seconds`,
   `window_seconds`, `n_observed_definition`, and `n_effective_definition`.
3. For long exports, inspect each row's `n_observed`, `n_effective`, and
   `n_effective_basis`.
4. Run `scripts/audit_recompute.py` against the patient cache. It checks row-count
   effective-N fields and reports cadence-adjusted fields as `not checked` if the
   necessary epoch-level independence marker or engine metadata is absent.
5. For MMX updates such as adding all-10-20 BSR or bilateral beta, reprocess cached
   patients before checking schemas and exports; stale caches will not reflect new
   MMX instruments.
6. **Sub-col contract validator** (`qeeg/ingestion/subcol_validator.py`, added 2026-05-21) must report zero errors for every cohort patient before cohort lock. The validator enforces the family-keyed schema in `qeeg/ingestion/subcol_schema.py`, which mirrors `PersystTrendCSV_Format_Reference.md` §3.0.
7. **There is no 30-minute averaging layer.** The template defines 52 TimeAvg instruments at 64 s and 120 s only. An audit script that expects a 1800 s layer is encoding a stale expectation and must be updated.
8. **`fft_beta_wide_*` (13–30 Hz) is pipeline-derived**, not a Persyst-native FFT_Power band. The audit must flag it as derived in the data dictionary; it inherits FFT cadence-adjusted N.
9. **Every patient in a cohort must be exported from the same MMX.** The I-group → family mapping is template-specific, so each patient's MMX hash belongs in provenance and the cohort lock must confirm one distinct hash. More than one hash is a protocol violation to investigate, not a missingness pattern to model — this release reads exactly one template.
