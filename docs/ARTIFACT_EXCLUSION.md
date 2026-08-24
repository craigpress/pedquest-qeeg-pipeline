# How artifact-affected values are excluded

**Audience:** anyone analysing the binned export or writing the methods section.
**Scope:** what is removed, when, why, and what each count in the output means.
**Code:** `qeeg/quality/ar_rejection.py`, `qeeg/quality/artifact_filter.py`, `qeeg/analysis/time_binning.py`.

There are **two independent mechanisms**. They answer different questions and are reported
separately; conflating them is the most likely way to misread the output.

| | Artifact-Reduction rejection | Artifact filter |
|---|---|---|
| Question | *Was this value ever measured?* | *Is this epoch clean enough to analyse?* |
| Unit | one value, in one region, in one epoch | the whole epoch |
| Result | value → `NaN` | epoch dropped from `usable_mask` |
| Reversible by config | `artifact.ar_rejection` (default **on**) | `artifact.mode` (default `quality`) |
| Reported as | `ar_*` fields in QC | `artifact_pct`, `usable_epochs` |

---

## 1. Artifact-Reduction rejection — values that were never measured

### The problem

Persyst writes **`0`, not blank**, when Artifact Reduction cannot produce a value. Those zeros are
missing data. Read as measurements they bias every mean, ratio and spectral summary downward, and
because they cluster in the most artifacted stretches the bias is systematic, not random.

Measured on subject-4 (0–6 h bin, `fft_delta_all`):

| | mean | `n_observed` |
|---|---:|---:|
| Suppressed zeros counted as data | 16.34 | 21,464 |
| Suppressed zeros excluded | **21.00** | 16,693 |

**+28.5%.** That is the size of the error this step removes.

### Why AR is the cause

Toggling AR on the same recording, same panel:

| | AR **on** | AR **off** |
|---|---:|---:|
| Region zero rate, worst / best | 24.5% / 0.10% | 0.12% / 0.10% |
| Rows with every region rejected | 0.10% | 0.10% |

With AR off every region is zero at an identical 0.12% — one real 37-second recording gap, which by
definition hits all channels at once. With AR on the rate varies 250-fold by region. Only **1.7%**
of AR-on zeros are also zero without AR, so **98.3% are AR rejections, not gaps**.

### Zero does not mean the same thing in every family

A rule that nulls any measure on its own zero destroys real data. Suppression Ratio is legitimately
`0` in **74%** of *clean* rows; a binary detector's `0` is a real "no event". So families are split
three ways, and only the first can seed the mask:

| Class | Families | Rule |
|---|---|---|
| **ZERO_IMPOSSIBLE** | `fft_spectrogram`, `fft_power`, `aeeg`, `peak_envelope`, `rhythmicity`, `coherence_spectrogram` | Physically positive-definite — an exact `0` cannot be a measurement, so its own zero **is** the signal. These build the mask. |
| **ZERO_LEGITIMATE** | `suppression_ratio`, `asymmetry`, `spectral_edge`, `adr`, `relative_power`, `alpha_variability` | Never inferred from their own value. Nulled **only** where the mask says their region was rejected. |
| **NEVER_NULL** | `rhythmic_delta`, `rda`, `sleep`, `spike_density`, all `seizure_*`, `status_epilepticus`, `artifact_detector`, `artifact_intensity`, `electrode_quality`, `heart_rate` | Zeros are measurements. Untouched — **except** when every region is rejected (below). |

### The rule

```
1. MASK — from ZERO_IMPOSSIBLE instruments only, per region:
       rejected[region, t] = every ZERO_IMPOSSIBLE instrument on that region
                             has all of its sub-columns == 0 at t
   A reference that is >=95% zero across the recording is excluded from the mask:
   a dead channel cannot tell you when rejection happened.

2. CLASSIFY at each t:
       every region rejected  -> RECORDING GAP
       some regions rejected  -> AR REJECTION, confined to those regions

3. APPLY:
       ZERO_IMPOSSIBLE  -> NaN on its own zero
       ZERO_LEGITIMATE  -> NaN where its region is rejected
       NEVER_NULL       -> untouched while ANY region survives;
                           NaN when EVERY region is rejected
       aggregates (All 10-20, Left Hemisphere) -> NaN on their own zero only
```

The raw export is never modified; the frame is copied.

**Why binaries still go NaN when everything is rejected.** A binary `0` means "no event" only if
there was signal to detect in. With every region rejected there was none — that is absence of input,
not absence of event. Counting those as true negatives would inflate the denominator of every burden
and rate calculation with epochs that were never assessed.

**Why regional, not per-row.** All regions are rejected together in only ~0.1% of rows while ~27%
are partial. A whole-row rule would both over-null good regions and under-null bad ones.

**Why aggregates are treated separately.** `All 10-20` is suppressed 20.2% while its worst
constituent channel is 51.9% — Persyst still averages when some channels survive. So an aggregate is
nulled on its own zero, never inferred from its constituents. The corollary: **a non-zero aggregate
does not mean all its channels contributed**, so the effective N behind each aggregate is unknown.

**Asymmetry fallback.** No positive-definite family is exported on the `Asym *` regions, so
asymmetry would never be nulled despite REASI being 100% zero inside a rejected epoch. `Asym Hemi` →
`All 10-20`/hemispheres, `Asym Anterior` → `Anterior`, `Asym Posterior` → `Posterior`,
`Asym Parasagittal`/`Temporal` → `All 10-20`.

**Empty segments.** If every positive-definite reference is ≥95% zero, no mask can be built. That is
an empty segment, not a rejected one: nothing is nulled, `ar_segment_empty` is set, and a warning is
raised. Such segments should be excluded before analysis.

---

## 2. Artifact filter — epochs excluded from analysis

Runs **after** AR rejection, on the corrected values. Modes: `none`, `intensity`, `detector`,
`quality` (default), `combined`. Whichever mode is selected, epochs where **AR rejected every
region** are always excluded — `mode="none"` means "apply no threshold", not "keep epochs that carry
no data". When that happens the method string becomes `<mode>+ar_rejection`.

Ordering matters and is deliberate: the artifact filter reads the same columns, so a suppressed `0`
read as a measurement makes an artifacted epoch look artifact-*free*.

---

## 3. How the statistics consume this

`summarize_bin` drops NaN before computing anything, so every statistic is over measured values only:

| Field | Meaning |
|---|---|
| `<var>_n_observed` | non-NaN values in the bin, **after** AR rejection — i.e. actually measured |
| `<var>_n_effective` | non-NaN values that are also independent observations at the engine's cadence |
| `<var>_effective_basis` | which independence rule produced `n_effective` |
| `<var>_mean` / `_median` / `_sd` / `_p05…_p95` / `_min` / `_max` | computed on non-NaN only |

**`n_observed` changed meaning as of 2026-08-22.** It previously counted suppressed zeros as
observations. Comparing an `n_observed` from before that date with one after is not valid.

A bin is emitted only if its artifact-clean coverage meets `min_coverage_hours`; otherwise every
statistic for that bin is `NaN` with `n_observed = 0`.

---

## 4. What to report in a methods section

Per patient, from `QCReport`:

| Field | Meaning |
|---|---|
| `total_epochs` / `usable_epochs` / `artifact_pct` | epoch-level exclusion |
| `ar_rows_all_rejected` | epochs where no region was analysable (also excluded as epochs) |
| `ar_rows_partial` | epochs analysed with **some regions missing** — these stay in the analysis |
| `ar_cells_nulled` | individual values set to NaN |
| `ar_region_reject_pct` | per-region rejection rate |
| `ar_segment_empty` | no analysable reference measure at all |

`ar_rows_partial` is the one that is easy to miss: those epochs are **not** in `artifact_pct`, they
are analysed with reduced spatial coverage.

Cohort as reprocessed 2026-08-22 (V10 afternoon exports, AR on):

| Patient | Epochs | Fully rejected | Partial | Cells → NaN | Artifact excl. |
|---|---:|---:|---:|---:|---:|
| subject-1 | 135,164 | 134 | 102 | 855,788 | 0.11% |
| subject-3 | 92,909 | 87 | 597 | 360,804 | 0.10% |
| subject-4 | 65,769 | 43,421 | 6,117 | 13,596,321 | 66.12% |
| subject-8 | 48,623 | 83 | 47 | 347,168 | 0.19% |
| subject-10 | 41,272 | 98 | 131 | 239,885 | 0.26% |
| subject-12 | 38,740 | 84 | 164 | 247,209 | 0.22% |
| subject-13 | 99,598 | 819 | 7,486 | 1,516,225 | 2.04% |

**subject-4 is not a heavily artifacted recording** — its 66% comes from a 99.94%-zero segment being
merged with the one good segment. Its per-value data is sound; its epoch count and coverage are not.
Excluding ≥95%-zero segments before the merge is an open item.

---

## 5. Recorded decision

**AR stays ON.** It reduces artifact contamination at the cost of channel-selective missingness,
which the rule above makes explicit rather than silent. The alternative — AR off — gives complete
coverage contaminated by artifact. State the choice and the per-recording rejection rate in the
methods.
