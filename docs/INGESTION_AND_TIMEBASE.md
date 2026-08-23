# Ingestion & Time Base — how a recording becomes analysis-ready

**Flagship doc #1.** For any subject/recording, this tells an analyst — with certainty and
citations — where the reference-event time **T0** comes from, how the **true recording start**
is derived, how multi-segment recordings and date-shifted files are handled, and **what every
exported column means**. Companion to [`EXPORT_AND_BINNING.md`](EXPORT_AND_BINNING.md).

Every claim cites `file:line`. The per-column reference it points to is
[`COLUMN_MAP_V10_RESEARCH_TRENDS.csv`](COLUMN_MAP_V10_RESEARCH_TRENDS.csv), regenerated from the
shipped template through the production resolution path.

---

## 1. The reference-event time T0 (ROSC)

- **Source.** T0 is the `rosc_time` field from a clinical/subject-alignment CSV, loaded via
  `SubjectRegistry.load_from_csv` (`subject_registry.py:35-68`), which auto-detects a ROSC column
  (`rosc_time` / `rosc` / `rosc_datetime`) and stores it as an **ISO datetime string** so it
  survives JSON round-trips (`subject_registry.py:60-65`). At run time:
  `rosc_ts = parse_rosc_time(rosc_time_str or cfg.rosc_time)` (`pipeline.py:143`).
- **Parsing.** `parse_rosc_time` (`alignment_check.py:53-86`) accepts Excel-serial numbers,
  numeric-string serials (guarded `1 < n < 2_958_465`), ISO/US datetime strings, and six explicit
  `strptime` formats; it returns **`None`** (never a bogus value) when unparseable.
- **Alignment guard.** `check_rosc_alignment` (`alignment_check.py:20-50`) validates the ROSC→EEG
  span. If EEG starts **>22 h** after ROSC (`MAX_ROSC_TO_EEG_HOURS=22.0`, `alignment_check.py:6`) the
  ROSC is treated as a probable date-shift mismatch and **discarded** (recording-relative fallback).
  If EEG starts **before** ROSC, pre-ROSC epochs are flagged for trimming.

> **Footgun (roadmap):** the ROSC column is matched by a fixed candidate-name list. A CSV using a
> non-listed header silently yields `rosc_time=None` → recording-relative time, with only a
> warning. Verify your metadata header matches.

## 2. The recording start (per-row timestamps)

- Each row's timestamp is the Persyst **`ClockDateTime`** column. The parser requires it: the code
  row must contain both I-codes and a `ClockDateTime` cell (`parser.py:121-136`) or ingestion
  **raises** (`parser.py:225`) — no silent fallback to row index.
- `ClockDateTime` is an **Excel serial date**, converted via `excel_serial_to_timestamp`
  (`parser.py:280-289`) with epoch **1899-12-30** (`timestamps.py:6`, absorbs the Excel 1900
  leap-year bug). Values outside `[1, 2_958_465]` become **NaT** (`timestamps.py:20-25`) rather than
  garbage.
- The recording start used for alignment is the first valid timestamp.

## 3. The time axis: hours relative to T0

- **`hours_relative = (timestamp − reference_time).total_seconds() / 3600`** (`time_axis.py:14-16`),
  exact, with pre-reference time naturally **negative**.
- Reference selection (`pipeline.py:146-148`): `effective_rosc = rosc_ts if alignment.is_aligned
  else None`; `build_time_axis(timestamps, effective_rosc)`. When ROSC is missing/unaligned the axis
  falls back to **recording start** and is **labeled** `reference="recording_start"`
  (`time_axis.py:19-28`) — carried into export provenance so ROSC-relative and recording-relative
  axes are never confused.
- **Pre-ROSC trimming.** When EEG precedes ROSC, epochs with `hours_relative < 0` are **discarded**
  (`pipeline.py:155-161`) with a logged `"Trimmed N epochs recorded before ROSC"`.

> **Design note (roadmap):** pre-ROSC epochs are *removed*, not merely labeled — a pre-arrest
> baseline will not appear in the binned export.

## 4. Multi-segment stitching

Continuation CSVs are merged by **semantic column name**, not raw row order
(`segment_merge.py:160-233`):

- Master time index = **sorted union of all `ClockDateTime`** across segments (`:213-220`).
- Disjoint time ranges concatenate; overlapping timestamps are resolved toward the
  **most-populated contributor** (`_merge_semantic_column:133-160`, ranked by non-null count).
- Each segment's raw I-codes are mapped to semantic `common_name`s first (`_rename_segment:73`), so
  **same-numbered I-groups in different CSVs do not collide** (the I-group-collision bug class).
- Requires unique `ClockDateTime` per segment (`:233` warns on duplicates).

## 5. Date-shift corrections

Date-shifted source files are handled by a corrections path keyed by the **`.dat` stem** (not the
CSV stem — the corrections-lookup-stem-mismatch fix), reconstructing synthetic timestamps and
validated by the **22 h guard** (§1). Covered by `tests/test_corrections.py` and
`tests/test_corrections_filter.py`. See `ARCHITECTURE.md §4.5`.

## 6. Cadence & independent observations

Rows are ~1 s apart, but engines update coarsely (FFT 8 s, Amplitude 10 s, Rhythmicity 2 s;
`cadence.py::FAMILY_ENGINE_MAP`). Effective-N counts *independent* observations, not rows — see
[`EXPORT_AND_BINNING.md` §4](EXPORT_AND_BINNING.md).

## 7. Known time-base caveats (from the audit; 0 refuted)

| # | Caveat |
|---|---|
| T8 | **Timestamps are tz-naive → DST-blind.** A recording crossing a daylight-saving boundary mis-measures elapsed hours by ~1 h. Fine for same-frame relative timing; document for cross-day recordings. |
| T4 | Pre-ROSC epochs are discarded (see §3). |
| T1 | ROSC column matched by fixed header list (see §1). |
| T2 | A numeric string in Excel-serial range is always parsed as a serial; datetime fallbacks are US month-first. |
| T9 | Correction-application code is test-covered but was not line-verified in the review pass. |

---

## 8. Column dictionary — what every exported column means

Column semantics have **three layered sources of truth**, in this order:

1. **The per-column map** —
   [`COLUMN_MAP_V10_RESEARCH_TRENDS.csv`](COLUMN_MAP_V10_RESEARCH_TRENDS.csv) (301 columns) and
   [`COLUMN_MAP_V10_FULL_RESEARCH_PANEL.csv`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.csv) (4,106).
   One row per exported column: I-code, CSV header, MMX instrument, `variable_name`, family,
   units, power scale, band, region, engine cadence, how the column was resolved, and an
   **evidence tier**. Generated by `scripts/gen_column_map_v10.py` through the same
   `build_column_schema_with_mmx` the pipeline uses, so it cannot drift from ingestion.
   There is an `.html` rendering of each for reading in a browser.
2. **Sub-column semantics** (sub-col count, bin frequencies, percentile order):
   [`qeeg/ingestion/subcol_schema.py`](../qeeg/ingestion/subcol_schema.py), mirroring
   `Ref Files/PersystTrendCSV_Format_Reference.md` §3.
3. **Family → unit / engine / value-range** (machine-checkable contract):
   [`persyst_families.generated.md`](persyst_families.generated.md), generated from code plus the
   shipped MMX and enforced by `tests/test_persyst_doc_sync.py`.

**Read the evidence tier before relying on a column.** `P-DOC` is vendor-documented, `P-COMM` a
direct Persyst communication, `MMX` read from the template, and `EMP` empirical or inferred.
`EMP` rows are provisional: they are our best reading of an undocumented export, not a
specification. Persyst publishes no CSV layout spec at all, so the format reference is
necessarily reverse-engineered and says so in its own header.

**Family units** (code-sourced; `persyst_families.generated.md` has the full generated table):

| Family | Unit | Sub-columns / notes | Evidence |
|---|---|---|---|
| `aeeg` | µV (peak-to-peak) | 5 percentiles: max, min, p50, p75, p25 (L/R/Ant/Post) | §3.4 |
| `artifact_intensity` | muscle µV; eye = probability 0–1 | 3 BSS components | §3.1 |
| `electrode_quality` | dimensionless, 0 = clean → 1.0; >1.0 = above the impedance disconnect threshold | 22 channels here, **numbered positionally** `esq_ch01…` — the export cannot support electrode identity, so none is asserted | §3.3 |
| `fft_power` | **µV (amplitude)** — the template sets `PowerType=1`, so this is not µV² power | per band × region | `export.py` |
| `fft_power_ratio` / `adr` / `alpha_variability` | ratio of **µV amplitudes** (dimensionless) | ADR = α/δ, TDR = θ/δ, RAV = 6–14/1–20. A conventional power-based ratio is the **square** of these | `export.py` |
| `relative_power` | fraction (0–1) | band ÷ native 1–30 Hz total | `export.py` |
| `fft_spectrogram` | µV/√Hz | 40 bins, k × 0.5 Hz | §3.12 |
| `spectral_edge` | Hz | SEF50/75/90/95 | `export.py` |
| `suppression_ratio` | **% (0–100)** | not a 0–1 fraction | §3.18 |
| `asymmetry` | **%** — EASI 0–100, REASI −100..+100 | | `export.py` |
| `rhythmicity` (+ spectrogram, FreqPow) | rhythmic amplitude µV/Hz | 97-bin **sqrt** axis; FreqPow is 4 bands × 4 values, not bins | §3.27 / §3.28 |
| `coherence_spectrogram` | coherence (0–1) | 63 bins; the broadband `Coherence_Avg` scalars are named by range, not by a bin | §3.15 |
| `seizure_probability` / `_detection` / `_notification` | probability 0–1 / boolean | plus Persyst-native status-epilepticus and seizure-burden metrics | `export.py` |
| `spike_density` | spikes/sec or per 10 s — the slug says which | per focus / hemisphere | `export.py` |
| `sleep` / `heart_rate` / `peak_envelope` | stage code / bpm / µV | | `export.py` |

**Two families are deliberately absent.** The 18 **Artifact Detector** columns are dropped at
ingestion — Persyst describes them as internal probabilistic classifiers rather than
measurements, and the per-electrode names the pipeline once gave them were invented, not read
from the export. Electrode **identity** for ESQ is likewise not asserted. See
[`ARTIFACT_EXCLUSION.md`](ARTIFACT_EXCLUSION.md).

---

_The `DATA_DICTIONARY_v4.md` snapshot is retained for cohort locks and links here._
