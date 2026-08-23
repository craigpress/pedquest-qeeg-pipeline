---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/plan
---

# Statistical Analysis Plan — Template

**Study:** _e.g. PedQuEST Outcome Prediction from qEEG Biomarkers_
**PI:** Craig A. Press, MD PhD
**Analysis lock date:** __
**Code commit:** __ (git SHA — see `audit_bundle.json`)
**Pipeline version:** __ (see `audit_bundle.json`)

## 1. Background and objectives

State the clinical question. Distinguish **primary**, **secondary**, and
**exploratory** objectives. Each exported variable will be labelled in the
analysis dataset accordingly.

## 2. Dataset

- **Source:** `.qeeg_cache/` cohort lock, frozen per
  [`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md).
- **Inclusion:** patients whose raw CSV + MMX + clinical metadata +
  corrections SHA-256 hashes are captured in the audit bundle, AND whose
  `subcol_validator` report contains zero error-severity mismatches.
- **Exclusion:** any patient whose `audit_bundle.json` reports
  `git.dirty=true`, a missing raw-input hash, or a non-empty
  `subcol_validator.errors` array.
- **MMX hash map:** record each patient's `mmx_fingerprint`. The cohort
  must resolve to exactly one distinct hash — this release reads a single
  template. A second hash is an export error to resolve before lock, not
  a covariate.
- **Time window:** [X] hours post-ROSC; bin edges = _e.g._
  `[0, 6, 12, 18, 24, 48, 72]`.
- **Minimum coverage per bin:** `clean_fraction_of_expected >= _e.g.
  0.5_`. Bins below this threshold are retained for descriptive reporting
  but excluded from inferential models.

## 3. Primary outcome

Define the dependent variable at the bin level and the mapping to
patient-level outcome. State the scale, unit, and whether log-transformed.

## 4. Feature set

| Feature family | Primary? | Transform | Bilateral policy | Notes |
|---|---|---|---|---|
| ADR (hemispheric) | yes | log10 | NaN-tolerant mean | `adr_avg_{side}_hemisphere` (120 s TimeAvg of FFT_PowerRatio 8-13//1-4) |
| TDR (hemispheric) | yes | log10 | require_bilateral=True | derived from `fft_power` 4–8 / 1–4 ratio |
| FFT delta power (anterior) | secondary | log10 | NaN-tolerant mean | `fft_delta_{side}_anterior`, µV² (not µV²/Hz) |
| Seizure burden (%) | yes | none (bounded [0,100]) | n/a | Persyst algorithmic — not adjudicated |
| BSR (suppression ratio) | yes | none (bounded **[0,100] percent**, NOT [0,1] fraction) | n/a | `suppression_{side}`; emitted on the percent scale per CSV ref §3.18 |
| aEEG envelope — primary | yes | none — bounded order statistic | n/a | **Pre-specify**: `aeeg_{side}_p50` (robust central tendency) OR `aeeg_{side}_max` / `min` (envelope extremes — classic clinical aEEG interpretation). The two are different inference targets. |
| aEEG envelope — dispersion | secondary | none | n/a | `aeeg_{side}_p75 − aeeg_{side}_p25` (IQR — derived if you want a robust within-window dispersion measure aligned with the new percentile sub-cols). |
| Rhythmicity spectrogram bin | exploratory | log10 (positive) | n/a | Slug `rhythmicity_{side}_{region}_{f}hz` where `f` is the 2-decimal **center** frequency from the **sqrt** axis, decimal point written as `_` (bin 49 = `9_00hz`). Bin spacing is non-linear — do not interpolate naïvely. |
| `fft_beta_wide_*` (13–30 Hz) | _flag as derived_ | log10 | NaN-tolerant mean | **Pipeline-synthesized** (sum of FFT_Spectrogram bins 13–30 Hz). NOT a Persyst-native FFT_Power band. Treat as derived; effective-N inherits FFT cadence-adjusted. |
| …add rows for every variable used | | | | |

## 5. Missingness and coverage

- `missingness_flag` categories: `complete`, `high_artifact`,
  `moderate_artifact`, `low_data`, `no_data`.
- Bins coded `no_data` or `low_data` are excluded from inferential
  models; bins coded `moderate_artifact` included with sensitivity
  analysis.
- Report patient-level cumulative coverage and flag cohort-level
  missingness patterns.
- **Panel-keyed missingness.** A column may be present in some patients
  and absent in others when they were exported from different *panels* of
  the same template — `Research-Trends` carries no spectrograms, and
  `Research-LimitedElectrodes` carries only single-chain derivations.
  Record each patient's resolved panel and pre-specify one of:
  - **(a) Restrict** the analysis to a single panel (state which).
  - **(b) Restrict** the analysis to the column subset present in
    **every** panel in the cohort.
  - **(c) Handle explicitly** — declare the column panel-dependent
    and model the version effect as a covariate (only defensible if the
    MMX version is approximately balanced across the outcome groups).

## 6. Statistical models

State the model class for each primary and secondary aim. Example:

- **Primary:** linear mixed-effects model, outcome ~ feature * time_bin +
  age + (1 | patient_id), REML; `lmer` in R / `statsmodels.mixedlm` in
  Python.
- Effect estimates with 95% CI; two-sided α = 0.05.
- Handling of repeated bins: random intercept for patient; time-bin as a
  categorical fixed effect.

## 7. Pre-specified covariates

_e.g._ age at arrest, sex, arrest location (IHCA vs OHCA),
initial rhythm, targeted temperature management status, sedation regime.

## 8. Sensitivity analyses

Each must be pre-specified. Examples:

- **Artifact mode:** re-run with `artifact_mode=combined` and compare
  effect sizes.
- **Seizure exclusion:** re-run with `SeizureConfig.exclusion_mode=none`
  vs. `probability`.
- **Bilateral fallback:** re-run with `require_bilateral=True` for all
  bilateral features.
- **Coverage threshold:** lower bound 0.3 vs 0.5 vs 0.7 for bin
  inclusion.
- **Bin edges:** compare 6h vs 4h bins.
- **Correction-time uncertainty:** jitter EEG correction timestamps by
  ±30 min and re-run.
- **Export-panel cohort split:** re-run the primary model restricted to
  each resolved export panel separately. Confirms the panel a patient was
  exported from is not a hidden confounder. State this even if the whole
  cohort came from one panel (negative control).
- **aEEG primary feature swap:** if the primary aim used `p50` (robust
  central), re-run with `max` (extreme upper envelope) as the primary,
  and vice versa. The two are different inference targets and should
  agree directionally if the clinical claim is robust.

## 9. Handling of multiple comparisons

State method (Bonferroni, Holm-Sidak, FDR/Benjamini-Hochberg) and the
family of tests it applies to.

## 10. Reproducibility

- Analysis runs on the cohort lock; no rerunning the pipeline during
  modelling.
- All model code committed to the analysis repo with a git tag matching
  the cohort lock tag.
- Final model outputs accompanied by the `audit_bundle.json` hashes.
- The SAP references a specific committed `docs/DATA_DICTIONARY_v{N}.md`
  by SHA-256. Column-name breaks (e.g. the 2026-05-21 aEEG
  `upper_margin → max` rename, the spectrogram bin slug format change
  `0-0.5hz → 0_50hz`, the rhythmicity sqrt-axis correction) require a
  major-version bump of the dictionary and a new SAP revision.

## 11. Deviations

Any deviation from this plan discovered during analysis must be logged
with date, rationale, and author. Deviation affecting primary outcome
testing requires PI approval before execution.

---

*Adapt this template per study. File the completed, signed SAP alongside
the cohort lock artefacts.*
