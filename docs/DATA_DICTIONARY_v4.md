---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# PedQuEST qEEG Data Dictionary (v4)

Generated from `build_data_dictionary()` with schema=None.
Snapshot of the column vocabulary at `COLUMN_SCHEMA_VERSION = 7`.

This file is a committed, human-readable snapshot of the machine-readable data
dictionary. It is regenerated from the pipeline via `build_data_dictionary()`
and committed alongside the code at each release. Any drift between this
snapshot and a fresh regeneration indicates a pipeline change that needs
review.

For per-patient entries with actual Persyst I-codes, generate the dictionary
with the patient schema attached; those entries depend on the patient CSV.

> **Canonical references.** Sub-column semantics and units mirror
> [`PERSYST_V10_REFERENCE.md`](PERSYST_V10_REFERENCE.md) §3a (Units canonical
> table), which itself mirrors
> `PersystTrendCSV_Format_Reference.md` §3. When this dictionary
> and §3a disagree, §3a wins.

## Regional, relative-power and Persyst-native event families

Column families that come from the template's non-lateralized channel sets and
its Persyst-native event metrics:

| Column family / pattern | Unit | Meaning | Notes |
|---|---|---|---|
| `rel_{band}_{location}` | fraction (0–1) | **Relative band power** = band ÷ total 1-30 Hz broadband. Persyst-native (`FFT PowerRatio {band}/1-30 Hz`). `{band}` ∈ delta/theta/alpha/beta_wide. | New family `relative_power`. `{location}` ∈ `all`, `anterior`, `posterior`, `{left,right}_{anterior,hemisphere,posterior}`. |
| `fft_{band}_anterior`, `fft_{band}_posterior` | µV | **Persyst-native** non-lateralized regional band power (whole-head Anterior/Posterior channel sets). | Takes precedence over the pipeline-computed bilateral aggregate of the same name (Persyst-native precedence). |
| `tdr_{location}` | ratio of µV amplitudes | **Theta-delta ratio** (4-8/1-4). | A distinct slug from `adr_*`; the two are separated by denominator, not by label. |
| `adr_{location}`, `rav_{location}`, `rel_*_{location}` with `_all` | — | Whole-brain ("All 10-20") ratio variants carry an explicit `_all` suffix (`adr_all`, `rav_all`, `rel_alpha_all`). | There is no bare `adr` slug — the region is always named. |
| `fft_{band}_{region}_asym`, `adr_{region}_asym`, `tdr_{region}_asym` | as base | Asymmetry-region power / ratio (Persyst `Asym Anterior/Posterior`). | The `_asym` suffix is emitted only when an `Asym` trend is actually present. This template carries `Asym` channels on the REASI indices only, so these columns do not appear in its exports. |
| `aeeg_anterior_*`, `aeeg_posterior_*` | µV | aEEG over the non-lateralized Anterior/Posterior channels. | — |
| `suppression_anterior`, `suppression_posterior` | % (0–100) | BSR over Anterior/Posterior channels. | Alongside `suppression_{left,right}[_{anterior,posterior}]` and `suppression_all`. |
| `sef_95_anterior`, `sef_95_posterior`, `peak_envelope_anterior`, `peak_envelope_posterior` | Hz / µV | SEF95 and PeakEnvelope over Anterior/Posterior channels. | — |
| `status_epilepticus_persyst_{method}_{output}` | binary 0/1 or % (0–100) | **Persyst-native** electrographic status epilepticus. `method` ∈ acns/advanced/combined; `output` ∈ binary/percent. ACNS method = ACNS 2021 ESE (≥10 continuous min OR ≥20% of any 60-min epoch). 10-s epoch/step. ⚠️ **Read the three cautions below before using the percent variants.** | **Does NOT replace** calculated `status_epilepticus_screen_flag` (≥30 min/≥50% screen) — both kept; different thresholds. ⚠️ Persyst seizure detection validated **adults ≥18 only** — research-use in pediatrics. See `PERSYST_V10_REFERENCE.md` §3b. |
| `seizure_burden_persyst_percentage` | % (0–100) | **Persyst-native** seizure burden — % of the 5-min epoch with seizure activity, updated every 10 s. | Source: Persyst QRG 6243-02. **Does NOT replace** `seizure_burden_pct` / `seizure_burden_hours`. ⚠️ adult-validated only. |
| `seizure_burden_persyst_category` | ordinal 0–3 | **Persyst-native** 5-min seizure-burden category: 0 = none/<30 s, 1 = ≥30–<150 s (Frequent), 2 = ≥150–≤270 s (Abundant), 3 = ≥270 s (Continuous). | Source: Persyst QRG 6243-02 / Help. See `PERSYST_V10_REFERENCE.md` §3b. |

**Relative power always uses the Persyst-native 1–30 Hz denominator** in this release. The pipeline's own band-sum fallback (denominator = δ+θ+α+β) is computed only when the native column is absent, which does not happen for exports from the shipped template. `mmx_fingerprint` is recorded per patient so the denominator in force is always recoverable.

### ⚠️ Status Epilepticus percent variants — read before modelling

Three vendor behaviours, confirmed in the **raw CSV** across 16 real exports
covering 7 patients. None is introduced by this pipeline, and none is repaired
by it — the values are transported faithfully and reported in QC
(`qc.constant_columns`, from `qeeg/quality/constant_columns.py`).

**1. The percent variants never reach zero.** Their resting output is a floor of
**0.050331**. On one 86,377-row recording, 73.1% of epochs sat exactly at that
floor and *no* epoch was 0. So:

- `status_epilepticus_persyst_advanced_percent > 0` is **true on every epoch of
  every recording**. It is not a detection criterion.
- A reported mean of "0.05%" is the floor, not a finding.
- Threshold **above** the floor, and say in the methods what threshold you used.

**2. `advanced_percent` and `combined_percent` are the same column.** They are
identical on every row of every export examined — including the recording with
406 distinct values, where they varied together exactly. Entering both in a
model is perfect collinearity; reporting both double-counts one measure. Pick
one and say which.

**3. `acns_percent` was exactly 0 in all 16 exports.** Either ACNS-criterion ESE
did not occur in this cohort, or the variant does not populate. Do not read a
zero here as evidence of absence without confirming the trend fires at all.

The **binary** variants behave as expected: 0/1, and 0 where nothing was
detected.

> A related caution applies to the eight `rhythmicity_thresh_*` columns, which
> were constant at 1 for whole recordings in this batch — they appear to export
> the configured detector threshold rather than a per-epoch detection. Treat a
> constant as a parameter until proven otherwise.

## Companion documents

- Code source of truth: [`qeeg/ingestion/subcol_schema.py`](../qeeg/ingestion/subcol_schema.py)
- Validator: [`qeeg/ingestion/subcol_validator.py`](../qeeg/ingestion/subcol_validator.py)
- Engine cadence: [`TREND_ENGINE_REFERENCE.md`](TREND_ENGINE_REFERENCE.md)
- Statistical methods: [`STATISTICAL_METHODS_AND_AUDIT.md`](STATISTICAL_METHODS_AND_AUDIT.md)

## Columns

### Identifiers & metadata

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| patient_id | identifier |  |  |  |  | Patient identifier |
| mmx_version | identifier |  |  |  |  | `LTMPage Version` of the MMX the patient was processed under. Paired with `mmx_fingerprint`; required because the I-group → family mapping is template-specific. |
| mmx_file_sha256 | identifier |  |  |  |  | SHA-256 of the MMX file used for this patient. |
| subcol_validator_passed | identifier | bool |  |  |  | True iff `qeeg.ingestion.subcol_validator` reported zero error-severity mismatches at parse time. Patients with `false` here are exclusion candidates per the SAP template. |
| time_bin | time |  |  |  |  | Time bin label |
| feature_name | export |  |  |  |  | Feature identifier |
| n_observed | export | rows |  |  |  | Observed row count contributing to feature summary |
| n_effective | export | observations |  |  |  | Effective independent observation count when cadence-adjusted |
| n_effective_basis | export |  |  |  |  | Interpretation of n_effective (see categorical map below) |
| n_independent_obs | time_binning | observations |  |  |  | Legacy bin-level effective observation count |
| missingness_flag | time_binning |  |  |  |  | Coverage/artifact status heuristic |
| meets_minimum | time_binning |  |  |  |  | Bin passes minimum coverage threshold |
| has_status_epilepticus | seizure |  |  |  |  | Status-epilepticus screen flag (deprecated name) |
| status_epilepticus_screen_flag | seizure |  |  |  |  | Status-epilepticus screen flag (algorithmic) |

### Bin-level summary statistics (applied to each feature)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| median | statistic | feature units |  |  |  | Feature median |
| mean | statistic | feature units |  |  |  | Feature arithmetic mean |
| sd | statistic | feature units |  |  |  | Feature standard deviation |
| p05 | statistic | feature units |  |  |  | Feature 5th percentile |
| p10 | statistic | feature units |  |  |  | Feature 10th percentile |
| p25 | statistic | feature units |  |  |  | Feature 25th percentile |
| p75 | statistic | feature units |  |  |  | Feature 75th percentile |
| p90 | statistic | feature units |  |  |  | Feature 90th percentile |
| p95 | statistic | feature units |  |  |  | Feature 95th percentile |
| iqr | statistic | feature units |  |  |  | Feature interquartile range |
| min | statistic | feature units |  |  |  | Feature minimum |
| max | statistic | feature units |  |  |  | Feature maximum |
| trimmed_mean_20pct | statistic | feature units |  |  |  | Feature 20 percent trimmed mean |
| cv | statistic | unitless |  |  |  | Feature coefficient of variation |
| log_mean | statistic | feature units |  |  |  | Feature geometric mean (positive values only; NOT applied to aEEG percentile columns) |
| log_sd | statistic | log units |  |  |  | Feature log standard deviation (positive values only; NOT applied to aEEG percentile columns) |
| slope | statistic | feature units per hour |  |  |  | Feature trajectory slope |

### Coverage fields (per bin)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| coverage_hours | time_binning | hours |  |  |  | Artifact-clean EEG support |
| bin_expected_hours | time_binning | hours |  |  |  | Configured bin width |
| observed_wall_clock_hours | time_binning | hours |  |  |  | Observed EEG support |
| artifact_clean_hours | time_binning | hours |  |  |  | Artifact-clean EEG support |
| clean_fraction_of_observed | time_binning | proportion (0–1) |  |  |  | Proportion clean (of observed EEG support) |
| clean_fraction_of_expected | time_binning | proportion (0–1) |  |  |  | Proportion of bin (clean coverage of configured bin width) |
| coverage_fraction | time_binning | proportion (0–1) |  |  |  | DEPRECATED alias of `clean_fraction_of_observed` |
| background_continuity_index | time_binning | proportion |  |  |  | Background continuity index |
| seizure_burden_hours | seizure | hours |  |  |  | Artifact-clean seizure burden in bin |
| n_effective_cadence_adjusted | time_binning | observations |  |  |  | Bin-level cadence-adjusted effective N |

### aEEG envelope percentiles (per CSV ref §3.4 — MMX-version-independent)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| aeeg_left_max  | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope maximum (p100), left hemisphere |
| aeeg_left_min  | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope minimum (p0), left hemisphere |
| aeeg_left_p50  | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope median (50th percentile), left hemisphere |
| aeeg_left_p75  | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope 75th percentile, left hemisphere |
| aeeg_left_p25  | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope 25th percentile, left hemisphere |
| aeeg_right_max | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope maximum (p100), right hemisphere |
| aeeg_right_min | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope minimum (p0), right hemisphere |
| aeeg_right_p50 | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope median, right hemisphere |
| aeeg_right_p75 | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope 75th percentile, right hemisphere |
| aeeg_right_p25 | aeeg | µV | 1 | 1 | aEEG01 | Smoothed envelope 25th percentile, right hemisphere |

> **Statistical note.** `max` and `min` are bounded order statistics; their
> sampling distributions are skewed. `p50` is the robust central-tendency
> target. IQR = `p75 − p25` is the appropriate within-window dispersion
> measure. Do NOT log-transform aEEG percentile columns. Pre-specify in the
> SAP whether primary inference uses `p50` (robust) or `max/min`
> (envelope extremes — classic clinical aEEG interpretation).

### FFT power (per CSV ref §3.5 — anterior and posterior bilateral summaries)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| fft_delta_anterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral anterior delta-band (1–4 Hz) FFT power |
| fft_delta_anterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_delta_anterior per epoch |
| fft_theta_anterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral anterior theta-band (4–8 Hz) FFT power |
| fft_theta_anterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_theta_anterior per epoch |
| fft_alpha_anterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral anterior alpha-band (8–13 Hz) FFT power |
| fft_alpha_anterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_alpha_anterior per epoch |
| fft_beta_anterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral anterior beta-band (13–20 Hz) FFT power |
| fft_beta_anterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_beta_anterior per epoch |
| total_power_anterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral anterior total FFT power |
| rel_delta_anterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative delta-band power, anterior |
| rel_theta_anterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative theta-band power, anterior |
| rel_alpha_anterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative alpha-band power, anterior |
| rel_beta_anterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative beta-band power, anterior |
| theta_delta_ratio_anterior | fft_power_ratio | dimensionless ratio | 8 | 4.0 | FFTEngine01 | Theta/Delta ratio, anterior |
| log_theta_delta_ratio_anterior | fft_power_ratio | log10 ratio | 8 | 4.0 | FFTEngine01 | log10(theta/delta) ratio, anterior |
| alpha_delta_ratio_anterior | fft_power_ratio | dimensionless ratio | 8 | 4.0 | FFTEngine01 | Alpha/Delta ratio, anterior |
| log_alpha_delta_ratio_anterior | fft_power_ratio | log10 ratio | 8 | 4.0 | FFTEngine01 | log10(alpha/delta) ratio, anterior |
| fft_delta_posterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral posterior delta-band (1–4 Hz) FFT power |
| fft_delta_posterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_delta_posterior per epoch |
| fft_theta_posterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral posterior theta-band (4–8 Hz) FFT power |
| fft_theta_posterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_theta_posterior per epoch |
| fft_alpha_posterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral posterior alpha-band (8–13 Hz) FFT power |
| fft_alpha_posterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_alpha_posterior per epoch |
| fft_beta_posterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral posterior beta-band (13–20 Hz) FFT power |
| fft_beta_posterior_sides_contributing | fft_power | count | 8 | 4.0 | FFTEngine01 | Hemispheres contributing to fft_beta_posterior per epoch |
| total_power_posterior | fft_power | µV | 8 | 4.0 | FFTEngine01 | Bilateral posterior total FFT power |
| rel_delta_posterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative delta-band power, posterior |
| rel_theta_posterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative theta-band power, posterior |
| rel_alpha_posterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative alpha-band power, posterior |
| rel_beta_posterior | fft_power_ratio | proportion (0–1) | 8 | 4.0 | FFTEngine01 | Relative beta-band power, posterior |
| theta_delta_ratio_posterior | fft_power_ratio | dimensionless ratio | 8 | 4.0 | FFTEngine01 | Theta/Delta ratio, posterior |
| log_theta_delta_ratio_posterior | fft_power_ratio | log10 ratio | 8 | 4.0 | FFTEngine01 | log10(theta/delta) ratio, posterior |
| alpha_delta_ratio_posterior | fft_power_ratio | dimensionless ratio | 8 | 4.0 | FFTEngine01 | Alpha/Delta ratio, posterior |
| log_alpha_delta_ratio_posterior | fft_power_ratio | log10 ratio | 8 | 4.0 | FFTEngine01 | log10(alpha/delta) ratio, posterior |

### Derived (pipeline-synthesized, NOT Persyst-native)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| fft_beta_wide_left_hemisphere  | fft_power (DERIVED) | µV | 8 | 4.0 | FFTEngine01 (synthesized) | Sum of FFT_Spectrogram bins 13–30 Hz, left hemisphere. **Not a Persyst-native FFT_Power band.** Inherits FFT cadence-adjusted effective N. |
| fft_beta_wide_right_hemisphere | fft_power (DERIVED) | µV | 8 | 4.0 | FFTEngine01 (synthesized) | Same, right hemisphere. |

### Suppression / BSR (per CSV ref §3.18 — emitted as **percent**, NOT fraction)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| suppression_left  | suppression_ratio | % (0–100) | 10 | 10.0 | Amplitude01 | Burst-suppression ratio, left hemisphere |
| suppression_right | suppression_ratio | % (0–100) | 10 | 10.0 | Amplitude01 | Burst-suppression ratio, right hemisphere |
| suppression_all   | suppression_ratio | % (0–100) | 10 | 10.0 | Amplitude01 | Burst-suppression ratio, whole-head (all 10-20) average |

### Spectral edge frequency (per CSV ref §3.19)

`sef_{percentile}_{channels_slug}` slug pattern; percentile ∈ {50, 75, 90, 95}; channels_slug ∈ {all, left_hemisphere, right_hemisphere, left_anterior, right_anterior, left_posterior, right_posterior, asym_anterior, asym_posterior}. Units: Hz (0–32).

### Asymmetry (per CSV ref §§3.10–3.11)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| asymmetry_easi_broadband_hemisphere   | asymmetry | % (0–100)    | 8 | 4.0 | FFTEngine01 | EASI (absolute) broadband 0–20 Hz, hemisphere |
| asymmetry_reasi_delta_hemisphere       | asymmetry | % (−100…+100) | 8 | 4.0 | FFTEngine01 | REASI delta (0–5 Hz), hemisphere |
| asymmetry_reasi_alpha_hemisphere       | asymmetry | % (−100…+100) | 8 | 4.0 | FFTEngine01 | REASI alpha (6–14 Hz), hemisphere |
| asymmetry_reasi_broadband_hemisphere   | asymmetry | % (−100…+100) | 8 | 4.0 | FFTEngine01 | REASI broadband (0–20 Hz), hemisphere |
| (+ regional variants for anterior, posterior, parasagittal, temporal) | asymmetry | % | 8 | 4.0 | FFTEngine01 | per-region REASI |

### Spectrogram bin slugs (per-bin columns)

Slug format: `<family>_<channel-group>_<center-freq>hz` where `<center-freq>`
is the 2-decimal **center** frequency in Hz, derived from
`qeeg.ingestion.subcol_schema.get_spectrogram_bin_freq()`:

| Spectrogram family | Bin formula | Example bin slugs |
|---|---|---|
| `fft_spectrogram` | linear, `f_k = k × 0.5 Hz` | `fft_spec_left_hemisphere_0_50hz` … `_20_00hz` (40 bins) |
| `asymmetry_spectrogram` | linear, `f_k = k × 0.5 Hz` | `asymmetry_spec_hemi_0_50hz` … `_20_00hz` (40 bins) |
| `coherence_spectrogram` | linear, `f_k = (k−1) × 32/62 Hz` | `coherence_spec_c3p3_0_00hz` … `_32_00hz` (63 bins). The single broadband `Coherence_Avg` scalars are named by their range instead: `coherence_avg_c3p3_0_32hz`. |
| `rhythmicity_spectrogram` | **sqrt-scaled**, `f_k = (1 + (k−1)/24)² Hz` | `rhythmicity_left_hemisphere_1_00hz`, `_1_09hz`, `_9_00hz`, … `_25_00hz` (97 bins, non-linear spacing) |

> **Important.** Rhythmicity spectrogram bins are NOT linearly spaced. Bin 49
> is at 9.00 Hz, NOT 13.0 Hz. Any analysis that indexes rhythmicity by bin
> number while assuming linear spacing is numerically wrong from bin ~10
> onward — read the frequency out of the slug, never off the bin index.

### Spike density (per CSV ref §3.24)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| spike_left          | spike_density | spikes/min (running rate) | 1 | 1 | SpikeDensityV101 | Left-hemisphere spike rate |
| spike_right         | spike_density | spikes/min | 1 | 1 | SpikeDensityV101 | Right-hemisphere spike rate |
| spike_generalized   | spike_density | spikes/min | 1 | 1 | SpikeDensityV101 | Generalized spike rate |
| spike_left_per_sec  | spike_density | spikes/s (count per 1-s epoch) | 1 | 1 | SpikeDensityV101 | Left spike count per 1 s |
| spike_left_per_10s  | spike_density | spikes/10s (count per sliding 10-s window) | 1 | 1 | SpikeDensityV101 | Left spike count per 10 s |
| (+ right, generalized, vertex, all_foci variants per suffix) | spike_density | as above | 1 | 1 | SpikeDensityV101 | per-laterality counts |

### Seizure (per CSV ref §3.22)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| seizure_probability_p14 | seizure_probability | probability (0–1) | 1 | 1 | SeizureProbabilityP1401 | P14 seizure probability |
| seizure_detection_p14   | seizure_detection   | binary (0/1)      | 1 | 1 | SeizureProbabilityP1401 | P14 detection flag |
| seizure_events          | seizure | event count (raw)               |  |  |  | Algorithmic seizure event count (raw) |
| seizure_events_artifact_clean | seizure | event count (artifact-clean) |  |  |  | Algorithmic seizure event count after artifact filtering |

### Heart rate (per CSV ref §3.16)

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| heart_rate | heart_rate | BPM | 1 | 1 | Heart Rate Engine01 | Heart rate derived from EKG channel |

### Artifact & electrode quality

| variable_name | family | unit | cadence_s | window_s | persyst_engine | label |
|---|---|---|---|---|---|---|
| artifact_intensity_emg | artifact_intensity | µV | 1 | 1.2 | Artifact01 | EMG (muscle) BSS component, µV magnitude |
| artifact_intensity_eye_vertical | artifact_intensity | probability (0–1) | 1 | 1.2 | Artifact01 | Vertical eye movement BSS component probability |
| artifact_intensity_eye_horizontal | artifact_intensity | probability (0–1) | 1 | 1.2 | Artifact01 | Lateral eye movement BSS component probability |
| esq_ch<NN> | electrode_quality | dimensionless | 1 | 1.2 | Artifact01 | Signal quality per acquisition channel, **numbered positionally** (22 channels here; count and order are recording-system dependent). 0 = clean → 1.0; >1.0 = above the impedance disconnect threshold. The electrode identity behind each position is not recoverable from the export and is deliberately not asserted — see `ARTIFACT_EXCLUSION.md`. |

## Categorical code maps

### n_effective_basis

| code | label |
|---|---|
| row_count | n_effective equals n_observed |
| fft_power_cadence_adjusted | Cadence-adjusted effective observation count for fft_power |
| fft_power_ratio_cadence_adjusted | Cadence-adjusted effective observation count for fft_power_ratio |
| alpha_variability_cadence_adjusted | Cadence-adjusted effective observation count for alpha_variability |
| fft_spectrogram_cadence_adjusted | Cadence-adjusted effective observation count for fft_spectrogram |
| spectral_edge_cadence_adjusted | Cadence-adjusted effective observation count for spectral_edge |
| suppression_ratio_cadence_adjusted | Cadence-adjusted effective observation count for suppression_ratio |
| rhythmicity_cadence_adjusted | Cadence-adjusted effective observation count for rhythmicity |
| rda_cadence_adjusted | Cadence-adjusted effective observation count for rda |
| periodic_discharge_cadence_adjusted | Cadence-adjusted effective observation count for periodic_discharge |
| asymmetry_cadence_adjusted | Cadence-adjusted effective observation count for asymmetry |
| not_estimated | Effective observation count not estimated for this feature family |

### missingness_flag

| code | label |
|---|---|
| complete | >=95% usable coverage |
| high_artifact | 50-94% usable coverage |
| moderate_artifact | 10-49% usable coverage |
| low_data | <10% usable coverage |
| no_data | 0 usable rows available |

### meets_minimum, has_status_epilepticus, status_epilepticus_screen_flag

| code | label |
|---|---|
| False | Criterion not met |
| True | Criterion met |

### {fft_band}_{region}_sides_contributing  (band ∈ {delta, theta, alpha, beta}; region ∈ {anterior, posterior})

| code | label |
|---|---|
| 0 | Neither hemisphere contributed |
| 1 | One hemisphere contributed (unilateral fallback) |
| 2 | Both hemispheres contributed (true bilateral mean) |

### sleep_stages (per CSV ref §3.23)

| code | label |
|---|---|
| 0 | Indeterminate (unscored) |
| 1 | N3 |
| 2 | N2 |
| 3 | N1 |
| 4 | REM |
| 5 | Wake |

---

*To regenerate this snapshot, run `build_data_dictionary()` against a patient
schema attached to a freshly reprocessed cohort patient. Bump the dictionary
major version (v4 → v5) on any column-name break.*
