# Export & Binning — the analysis-ready dataset

**Flagship doc #2.** What the binned summary export contains, how bins and statistics are
defined, how effective-N and coverage gating work, what units apply, and how to load it into
R / Python / Stata. Companion to [`INGESTION_AND_TIMEBASE.md`](INGESTION_AND_TIMEBASE.md)
(time base + per-column dictionary). Every claim here cites `file:line`; the authoritative
machine-checkable family contract is [`persyst_families.generated.md`](persyst_families.generated.md).

> **Anti-drift:** unit and family facts are generated from code registries
> (`export.py::_FAMILY_UNITS`, `cadence.py::FAMILY_ENGINE_MAP`, `data_checks.py::FAMILY_VALUE_RANGES`)
> by `scripts/sync_persyst_docs.py`. Do not restate them elsewhere — link here or to the generated table.

---

## 1. The time axis

Every row is placed on **`hours_relative`** — hours from the reference event T0
(`time_axis.py:14-16`, exact `(timestamp − reference)/3600`). The reference is **ROSC when
available, else recording start**, and the choice is labeled in the export provenance
(`reference ∈ {"rosc","recording_start"}`, `time_axis.py:19-28`). See
[`INGESTION_AND_TIMEBASE.md`](INGESTION_AND_TIMEBASE.md) for T0 derivation, the 22 h alignment
guard, and pre-ROSC trimming.

## 2. Bin definitions

- Default edges (hours): **`[0, 6, 12, 18, 24, 48, 72]`** (`constants.py:55 DEFAULT_BIN_EDGES_HOURS`); configurable per run.
- Bins are **half-open, left-closed `[start, end)`** — `pd.cut(..., right=False, include_lowest=True)` (`time_binning.py:38`). A value exactly on an edge belongs to the bin that *starts* at that edge.
- Each bin row carries **`bin_label`, `bin_start_hours`, `bin_end_hours`** (`export.py:80`).
- ⚠️ **Epochs outside the configured edges (>72 h, or pre-origin <0 h) are currently dropped without a count** (`time_binning.py:232`; roadmap P1-3). Until fixed, confirm your edges span the recording.

## 3. Per-bin summary statistics

For each analysis feature, per bin (`time_binning.py:142-180`, defined in `export.py:341-358`):

| Suffix | Meaning | Units |
|---|---|---|
| `_median` | Median of usable, non-null values (after the effective-N mask) | feature units |
| `_mean` | Arithmetic mean | feature units |
| `_sd` | Sample SD (0.0 when one value contributes) | feature units |
| `_p05 _p10 _p25 _p75 _p90 _p95` | Empirical percentiles | feature units |
| `_iqr` | p75 − p25 | feature units |
| `_min _max` | Extremes | feature units |
| `_trimmed_mean_20pct` | Mean after trimming 10% each tail; = mean for <4 obs | feature units |
| `_cv` | SD/mean, **only for strictly positive mean** (NaN for zero/near-zero/negative) | unitless |
| `_log_mean` | **Geometric mean** `exp(E[ln x])`, **positive spectral-power families only** | feature units |
| `_log_sd` | SD of `ln x` (positive spectral-power only) | log units |
| `_slope` | Linear-regression slope of bin midpoint vs feature median across covered bins | feature units per hour |

**Why geometric/log stats exist:** FFT power and power-ratio families are right-skewed and
multiplicative; the arithmetic mean is misleading. Log-transform families are gated in
`time_binning.py:9 _LOG_FAMILIES`. Geometric 95% CI = `log_mean × exp(±1.96 × log_sd)`.

## 4. Effective-N (independent observations, not raw rows)

1-second Persyst rows are **not independent** — engines update at coarser cadence (FFT every 8 s,
Amplitude every 10 s, Rhythmicity every 2 s, …; `cadence.py::FAMILY_ENGINE_MAP`,
`FFT_UPDATE_INTERVAL=8`). Counting every row would overstate N and understate variance
(pseudoreplication).

| Column | Meaning |
|---|---|
| `{feat}_n` | Raw usable, non-null value count |
| `{feat}_n_effective` | Cadence-adjusted independent-observation count (`time_binning.py:159`) |
| `{feat}_effective_basis` | How it was derived: `row_count`, `{family}_cadence_adjusted`, or `not_estimated` (`cadence.py:106-123`) |
| `n_effective_fft`, `n_effective_cadence_adjusted` | Per-bin effective-observation totals |

The independent-observation mask (`derived_features.py:113-157`) detects FFT value transitions
with a fixed-interval fallback for constant (burst-suppression/isoelectric) epochs.
**Caveat:** this reduces but does not eliminate within-bin autocorrelation — treat repeated
within-bin observations accordingly in mixed models (roadmap: biostatistics).

## 5. Coverage gating

| Column | Meaning | Source |
|---|---|---|
| `coverage_hours` | Usable EEG hours in the bin | `time_binning.py:264` |
| `coverage_fraction` | Usable / expected | `time_binning.py` |
| `bin_expected_hours`, `observed_wall_clock_hours` | Bin width and wall-clock observed | `export.py:84` |
| `artifact_clean_hours` | Artifact-clean usable hours (coverage numerator) | `time_binning.py:263` (roadmap P1-2: confirm it reflects usable EEG time, not wall-clock) |
| `clean_fraction_of_observed`, `clean_fraction_of_expected` | Clean fractions | `export.py:85` |
| `meets_minimum` | `coverage_hours ≥ MIN_BIN_COVERAGE_HOURS` (default **1.0 h**, `constants.py:323`) | `time_binning.py:266` |
| `background_continuity_index`, `seizure_burden_hours` | Derived per-bin clinical summaries | `export.py:86`. BCI thresholds BSR at the ACNS 2021 continuous/discontinuous boundary of **10%** (Hirsch et al., *J Clin Neurophysiol* 2021;38(1):1-29) |

Acquisition gaps are capped at 3× the median step so dropouts don't inflate observed time
(`time_binning.py:75 infer_epoch_durations_hours`).

## 6. Missingness — no silent imputation

Missing/insufficient data is **never imputed**. An empty or below-threshold bin yields **NaN**
for every statistic and `n_effective=0` with `effective_basis="not_estimated"`
(`time_binning.py:289-293`). On write: **blank field (CSV) / null (parquet)** — no sentinel codes
(`export.py:336-340`). A per-bin **`missingness_flag`** encodes the coverage tier
(`export.py:70-76`):

| Flag | Coverage |
|---|---|
| `complete` | ≥95% usable |
| `high_artifact` | 50–94% |
| `moderate_artifact` | 10–49% |
| `low_data` | <10% |
| `no_data` | 0 usable rows |

## 7. Feature families & units

Units come from `export.py::_FAMILY_UNITS` (generated into
[`persyst_families.generated.md`](persyst_families.generated.md)). Selected values:

| Family | Unit | Note |
|---|---|---|
| `fft_power` | **µV (amplitude)** — the template sets `PowerType=1` | not µV² power, not µV²/Hz |
| `fft_power_ratio`, `adr`, `alpha_variability` | ratio of **µV amplitudes** (dimensionless) | a conventional power-based ratio is the **square** of these — say which convention you used |
| `relative_power` | fraction (0–1) | native 1–30 Hz denom vs computed band-sum differ |
| `fft_spectrogram` | µV/√Hz (ASD; square → PSD µV²/Hz) | |
| `spectral_edge` | Hz | |
| `suppression_ratio` (BSR) | **% (0–100)** | resolved against real exports (format reference §3.18); not a 0–1 fraction |
| `aeeg` | µV (peak-to-peak) | 5 percentiles max/min/p50/p75/p25 |
| `asymmetry` | **%** | EASI 0–100, REASI −100..+100 |
| `seizure_probability` | probability (0–1) | |
| `seizure_detection`/`_notification` | boolean (0/1) | |
| `spike_density` | spikes/sec or per 10 s | the slug says which — `_per_sec` vs `_per_10s` |
| `coherence_spectrogram` | coherence (0–1) | |
| `heart_rate` | bpm | |

Full per-column meanings: [`INGESTION_AND_TIMEBASE.md` §8](INGESTION_AND_TIMEBASE.md) and the
generated [`COLUMN_MAP_V10_RESEARCH_TRENDS.csv`](COLUMN_MAP_V10_RESEARCH_TRENDS.csv).

## 8. Output shapes

| Shape | What | Use |
|---|---|---|
| **Wide `bin_summary`** | One row per (patient, bin); columns = `{feature}_{stat}` + bin metadata | Primary analysis table |
| **Long / tidy** | One row per (patient, bin, feature, statistic) | ggplot / tidyverse, mixed models |
| **Parquet** | Columnar, typed, null-aware | R `arrow`, Python `pandas`/`polars`, DuckDB |
| **Cohort batch** | All patients concatenated into one file with a `patient_id` column | R/Stata/Python cohort analysis (memory: batch-all-patients preference) |

## 9. Loading the export

```python
# Python
import pandas as pd
df = pd.read_parquet("bin_summary.parquet")          # nulls = missing, never imputed
```
```r
# R
library(arrow); df <- read_parquet("bin_summary.parquet")   # NA = missing
```
```stata
* Stata: export CSV; blank = missing
import delimited "bin_summary.csv", case(preserve)
```

**Read this before analysis:** a value is missing when the cell is blank/NA — do not fill it.
Weight by `{feat}_n_effective`, not `{feat}_n`. Gate on `meets_minimum` / `missingness_flag`.
Use `_log_mean` (geometric) for power families. Note that FFT power and every ratio built from
it are **amplitudes**, not powers — see the units table above before comparing to published
figures.

---

_Supersedes the overlapping column/stat material in `DATA_DICTIONARY_v4.md` and
`TREND_ENGINE_REFERENCE.md` (retained as cohort-lock snapshots that link here)._
