---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/review
---

# Statistical Reviewer Checklist

Pass/fail checks a reviewer (statistician, IRB, journal editor) should run
against a cohort lock before accepting the analysis. Each item has a
verification command or file reference.

## Provenance

- [ ] **Every raw input has a SHA-256 hash.**
  Check: `jq '.inputs.raw[] | select(.sha256 == null)' audit_bundle.json`
  returns empty.
- [ ] **MMX file hash captured per patient, and single-valued across the cohort.**
  Check: `jq '[.patients[].mmx_fingerprint] | unique | length' audit_bundle.json`
  returns `1`. Required because the I-group → family mapping is
  template-specific: two hashes mean two column vocabularies, and any
  cross-patient join is then unsafe.
- [ ] **Sub-col contract validator report is in the audit bundle and contains
  zero error-severity mismatches.**
  Check: `jq '.subcol_validator.errors | length' audit_bundle.json` returns
  `0`. Warn-severity mismatches (e.g. Electrode Signal Quality channel count
  varying by acquisition system) are acceptable but must be enumerated.
  Required because the validator is the single line of defense against
  silent slug drift across MMX versions — see
  `qeeg/ingestion/subcol_validator.py`.
- [ ] **Clinical metadata and corrections hashed (if used).**
  Check: `jq '.inputs.auxiliary' audit_bundle.json`.
- [ ] **Git commit captured and clean.**
  Check: `jq '.git' audit_bundle.json`; `dirty` must be `false`.
- [ ] **Pipeline version and cache-schema match the code at that commit.**
  Check: `jq '.pipeline' audit_bundle.json` against
  `qeeg/__version__.py` and `qeeg/storage/result_cache.py:CACHE_SCHEMA_VERSION`
  at the tagged commit.

## Processing configuration

- [ ] **Artifact mode is pre-specified.**
  Check: `jq '.config.artifact.mode' audit_bundle.json`. PedQuEST/POCCA
  default = `"quality"`; any other value must be justified in the SAP.
- [ ] **Seizure exclusion mode stated.**
  Check: `jq '.config.seizure.exclusion_mode' audit_bundle.json`.
- [ ] **Bin edges match SAP.**
  Check: `jq '.config.binning.bin_edges_hours' audit_bundle.json`.
- [ ] **Minimum coverage threshold matches SAP.**
  Check: `jq '.config.binning.min_coverage_hours' audit_bundle.json`.
- [ ] **ROSC anchor present for every patient.**
  Check: `meta.json > time_info.reference == "rosc"` for each cached
  patient; any `"recording_start"` fallback must be listed in the SAP.

## Data-dictionary integrity

- [ ] **Every exported column has a dictionary entry.**
  Check: column set from `bin_summary.parquet` and `epochs.parquet` is a
  subset of variable names in `data_dictionary.json`.
- [ ] **Every Persyst-sourced feature has a non-empty unit.**
  Check: `jq '.[] | select(.original_code != "" and .unit == "")'
  data_dictionary.json` returns empty.
- [ ] **Derived features (`total_power_*`, `rel_*_*`,
  `{theta|alpha}_delta_ratio_*`, `log_*_ratio_*`, `fft_*_sides_contributing`,
  `fft_beta_wide_*`) each have a dictionary entry AND are flagged as
  `derived: true`.**
  `fft_beta_wide_*` (13–30 Hz) is **NOT** a Persyst-native FFT_Power band
  — it is pipeline-synthesized from FFT_Spectrogram bins. The
  dictionary entry must reflect this and the SAP must treat it as derived,
  not as a primary instrument output.
- [ ] **aEEG columns use the canonical percentile slugs.**
  Check: every `aeeg_{side}_*` column ends with one of
  `_max`, `_min`, `_p50`, `_p75`, `_p25`. No patient cache may contain
  the legacy slugs `upper_margin`, `lower_margin`, `bandwidth`,
  `percent_bs`, `amplitude`. Per `PersystTrendCSV_Format_Reference.md`
  §3.4, these are statistical percentiles of the smoothed envelope
  (MMX-version-independent), not Persyst-specific quantities.
- [ ] **Units sanity check.**
  Cross-reference `data_dictionary.json` unit strings against
  `PERSYST_V10_REFERENCE.md` §3a (Units canonical table). Notable items:
  - BSR / suppression columns: `% (0–100)` — NOT fraction (0–1).
  - FFT_Power columns: `µV` (amplitude; the template sets `PowerType=1`) — NOT µV², NOT µV²/Hz.
  - ADR / RAV / relative power are ratios of **amplitudes**. A power-based
    ratio is the square of the exported value — state which convention the
    analysis uses before comparing to published figures.
  - FFT_Spectrogram columns: `µV/√Hz` (square root of power) — square
    to recover µV²/Hz.
  - Rhythmicity spectrogram bin labels follow sqrt-scaled formula
    `f_k = (1 + (k−1)/24)²` (bin 49 = `9_00hz`, NOT 13hz from the legacy
    linear approximation).
- [ ] **`missingness_flag` category codes match exported values.**

## Denominator and coverage semantics

- [ ] **Two coverage fields are labelled explicitly:**
  - `clean_fraction_of_observed` = **proportion clean** (of recorded EEG)
  - `clean_fraction_of_expected` = **proportion of bin** (of configured bin width)
  The methods section names which one drives bin inclusion.
- [ ] **`coverage_fraction` is deprecated.** Not used in any
  publication-bound table; flagged as alias of `clean_fraction_of_observed`.
- [ ] **`missingness_flag` policy is pre-specified in the SAP.**
- [ ] **`n_effective_basis` is correctly interpreted per feature.**
  Row-count families may use `n_observed`; cadence-adjusted families
  must use `n_effective`.
- [ ] **Slopes interpreted as patient-level scalars, not time-varying
  features.** `*_slope` is broadcast to every bin row.

## Seizure metrics

- [ ] **Raw vs artifact-clean seizure event metrics are distinguished in
  the publication table.** `seizure_events` (raw) and
  `seizure_events_artifact_clean` are different denominators.
- [ ] **Status-epilepticus labelled as screening only** (not ILAE
  adjudication), unless clinical adjudication is independently
  performed and documented.

## Bilateral features

- [ ] **`require_bilateral` policy is stated in the SAP.** Default is
  `False` (NaN-tolerant mean). Review the `fft_{band}_{region}_sides_contributing`
  distribution in the cohort; unilateral-dominant cases are a
  methodological concern in asymmetric encephalopathy.

## Independent recompute

- [ ] **`scripts/audit_recompute.py` passes against every cohort patient.**
  Zero mismatches; zero `not_checked` for fields used in the
  publication.
- [ ] **Sensitivity analyses pre-specified in the SAP are executed and
  reported.**

## Template and panel handling

- [ ] **Cohort resolves to exactly one MMX.**
  Check: `jq '[.patients[].mmx_fingerprint] | unique' audit_bundle.json`
  returns a single hash. This release reads one template; a second hash is
  an export error to resolve before lock, not a covariate to adjust for.
- [ ] **Panel-keyed missingness is pre-specified in the SAP.**
  Patients exported from different panels of the same template carry
  different column sets — `Research-Trends` has no spectrograms,
  `Research-LimitedElectrodes` only single-chain derivations. Check the
  resolved panel per patient. If a column exists for some patients but not
  others for this reason, the SAP must say whether the analysis
  (a) restricts to a single panel, (b) handles per-panel availability
  explicitly, or (c) drops the column.
- [ ] **Column-resolution method is reported.**
  Check `column_resolution.fully_ordinal` is `true` for every patient.
  `false` means the panel could not be identified and columns were
  classified from text — a weaker identity claim that must be disclosed.

## Ten council questions (from Research Readiness Review)

- [ ] **Q1.** Primary vs secondary vs exploratory endpoints documented.
- [ ] **Q2.** SAP frozen before unblinding.
- [ ] **Q3.** Seizure metrics identified as algorithmic vs adjudicated.
- [ ] **Q4.** Bin denominator choice (expected vs observed) stated.
- [ ] **Q5.** Per-bin / per-patient coverage thresholds stated.
- [ ] **Q6.** Seizure epochs excluded/included policy stated.
- [ ] **Q7.** Bilateral fallback policy stated.
- [ ] **Q8.** Input versioning / freeze procedure documented.
- [ ] **Q9.** Independent validation path (e.g. hand-calculation or
  Persyst-display comparison) documented.
- [ ] **Q10.** Sensitivity analyses for artifact mode, seizure threshold,
  coverage threshold, bin edges, correction-time uncertainty.

All ten must be answered (not necessarily "yes") before analysis lock.
