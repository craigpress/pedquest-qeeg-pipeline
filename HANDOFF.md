---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - type/handoff
---

# HANDOFF — PedQuEST qEEG Analysis Pipeline

**State as of 2026-08-23.** Version **4.0.0**, column vocabulary **v8**.
Suite: **647 passed, 12 skipped**.

This is the cross-tool handoff file. It records what the pipeline does, what it
deliberately refuses to do, and what is still open. Verify before acting — it is
a dated observation, not live state.

---

## 1. What this is

Ingests Persyst qEEG trend CSV exports, resolves every column to a stable
identifier, time-bins the result relative to a reference event (ROSC), and emits
analysis-ready datasets plus an interactive dashboard.

```bash
pip install -e .
cd frontend && npm install && npm run build && cd ..
python start.py
```

Read [`docs/INDEX.md`](docs/INDEX.md) first; it routes every topic to one
source-of-truth file. The two flagship docs are
[`docs/INGESTION_AND_TIMEBASE.md`](docs/INGESTION_AND_TIMEBASE.md) and
[`docs/EXPORT_AND_BINNING.md`](docs/EXPORT_AND_BINNING.md).

## 2. One template, and why it matters

```
Ref Files/PedQuEST_Pennsieve_V10_research.mmx
sha256 213ebcd7dece6b61d86b33b78cf0d462d35736bd4456193eaf54a095384a397a
22 panels · 10 engines · 370 instruments · 962 panel-slot references
```

Column identity comes from an instrument's **position in its export panel**:

```
len(panel.instruments) + 2 == max(i_group)     the +2 is Persyst's Comment and Time tail
```

That invariant holds with zero violations across the real exports
(`Research-Trends` 238 + 2 → `I240`, `Research` 370 + 2 → `I372`). It is a
property of *this template* — an export from a different MMX resolves to
different columns under the same names. So:

- Every patient's MMX fingerprint goes into provenance, and **a cohort must
  resolve to exactly one**. Two fingerprints mean two vocabularies and no safe
  cross-patient join.
- Earlier templates live in `_archive/` for provenance only. They are not
  readable by this release, and no doc describes them.

Names never encode absolute I-numbers — those shift whenever the panel is
edited. Where the panel cannot be identified, resolution degrades to name then
regex, and every column records which method applied; exports publish the mix.

## 3. What is deliberately excluded

Both exclusions exist because the alternative was asserting an identity the
export cannot support. Documented in [`docs/ARTIFACT_EXCLUSION.md`](docs/ARTIFACT_EXCLUSION.md).

| Excluded | Why |
|---|---|
| The 18 **Artifact Detector** columns | Persyst (2026-08-20) describes them as internal probabilistic classifiers, not per-electrode measurements. The pipeline had been naming them positionally from a hardcoded BP-Longitudinal list and labelling them "binary 0/1" — both invented; on 4290-1 all 18 carry `raw_name = null`, so those electrode names were never read from the CSV. Dropped at ingestion via `constants.DISCARDED_FAMILIES`, before anything reads the frame. |
| **Electrode identity** for Signal Quality | Channel order and count vary by recording. The old hardcoded 22-entry list was wrong in 21 of 22 positions and turned a real disconnect pattern into a fabricated one. ESQ is emitted positionally as `esq_ch01…esq_chNN`; identity travels as per-recording metadata or not at all. |

A third rule is enforced by test rather than by exclusion: a `__dupN`
uniqueness-backstop name must never reach a published column map
(`tests/test_column_map_artifacts.py`). The backstop keeps ingestion from
silently dropping a column, but the name it produces identifies nothing.

## 4. Units — the two that get misread

Both are stated wherever they matter, but they are the errors most likely to
survive into a manuscript:

- **FFT power is µV (amplitude), not µV².** The template sets `PowerType=1`.
  Consequently **ADR, TDR, RAV and relative power are ratios of amplitudes** — a
  conventional power-based ratio is the **square** of the exported value. Say
  which convention you used before comparing to published figures.
- **Suppression Ratio is % (0–100), not a 0–1 fraction.** Resolved against real
  exports and format reference §3.18. `background_continuity_index` thresholds
  it at the ACNS 2021 continuous/discontinuous boundary of 10% (Hirsch et al.,
  *J Clin Neurophysiol* 2021;38(1):1-29).

There is **no 30-minute (1800 s) averaging layer** in this template — 36
instruments at 120 s and 16 at 64 s. Averaged columns are smoothed views of a
raw trend, never independent variables alongside their own source.

## 5. What has been verified against a real full-panel export

**16 full-panel exports, 7 patients, 15.0 GB** — the first batch carrying the
spectrogram families, so the first that could exercise the whole path.
**14 of 16 passed 29/29.** Full write-up:
`docs/_project/diagnostics/2026-08-23-full-panel-batch-verification.md`.

```bash
python scripts/verify_batch.py                      # every full-panel export
python scripts/verify_full_panel.py --scan          # find one
python scripts/verify_full_panel.py <export.csv>    # check one
```

Identical on every passing export, across all 7 patients:

| Check | Result |
|---|---|
| Panel resolution | 4,086 ordinal + 2 tail, **zero** columns falling back to name or regex |
| `common_name` uniqueness | 4,088 names, all unique, all valid identifiers, no `__dupN` |
| Artifact Detector discarded | confirmed absent from the schema and the frame |
| FFT spectrogram L/R | 40 bins, 0.50–20.00 Hz |
| Asymmetry spectrogram | 40 bins, 0.50–20.00 Hz |
| Coherence spectrogram | 63 bins, 0.00–32.00 Hz (bin-1 convention still open — item 3) |
| Rhythmicity spectrogram | 97 bins, 1.00–25.00 Hz on the sqrt axis |
| NaN transport | 0.3 M – 42.9 M AR-rejected cells per export, always across the same 3,937 columns, none leaking as bare NaN |

The panel-ordinal invariant holding at **zero** regex fallbacks across 15 GB of
independent recordings is the strongest evidence yet for the resolution scheme.

That run also found a real bug. The bare `asymmetry` spec_type was missing from
`_schema_family_for_spec_type`, so its axis came from the
`freq_min + (k-1) * resolution` fallback instead of the schema formula:
**0.00–19.50 Hz instead of 0.50–20.00**, every bin labelled half a bin low and
the 20 Hz bin off the end. Fixed, with `tests/test_spectrogram_axes.py` now
asserting that every spec_type resolves to a real schema — a missing key does
not raise, it silently returns a plausible wrong axis.

## 6. Open items

| # | Item | Notes |
|---|---|---|
| 1 | **4290-4 lost 12.1 h to disconnected electrodes** | `4290-4_2e68997/20260823_1800_.csv` (2024-06-13 18:55 → 06-14 07:00) has all 22 ESQ channels pinned at the 1.2 display maximum — above the impedance disconnect threshold — for essentially the whole segment, and 99.94–99.96% exact zeros in every EEG family. The EKG kept producing (implausible) values, so the amplifier was running with nothing usable attached. **Not superseded**: the other 4290-4 export covers 2024-07-13, a different month. Exclude the segment; decide whether the June recording is recoverable from the source `.dat`. |
| 2 | **`4290-1_1684730/20260823_1749_.csv` is malformed — safe to delete** | 8,215-cell header row against 4,108-wide data rows: a data row was written onto the end of the header without a newline, fusing `I372_1` to the timestamp `45330.7752777778`. The parser refuses it rather than guessing. Its 12.4 h span is fully contained by `20260823_1802_.csv` (24.0 h), which passes, so nothing is lost. |
| 3 | **Status Epilepticus percent variants need care** | Three vendor behaviours, confirmed in the raw CSV across all 16 exports. The percent variants **never reach 0** — their floor is 0.050331, so `> 0` fires on every epoch of every recording and a mean of "0.05%" is the floor, not a finding; threshold above it and say so. `advanced_percent` and `combined_percent` are **identical on every row** — one variable, two names, perfectly collinear. `acns_percent` was **exactly 0 in all 16** exports. The binary variants are fine. Reported per recording in `qc.constant_columns`; written up in `docs/DATA_DICTIONARY_v4.md`. |
| 4 | **A constant column is a parameter until proven otherwise** | The same survey flagged eight `rhythmicity_thresh_*` columns constant at 1 for whole recordings — `_gte_1_1hz` reads like "criterion met" but a value that never varies is a configured threshold. It also found ten pairs where `rhythmicity_freqpow_{region}_1_4hz_*` is identical to `rhythmicity_sum_{region}_delta_*`. Neither is confirmed with Persyst yet. |
| 5 | **`heart_rate_2` identity unconfirmed** | The template ships "Heart Rate" and its "Heart Rate01" alias, exporting as two columns under headers "Heart Rate 1" / "Heart Rate 2". Whether they carry distinct signals is unknown — tier EMP. Ask Persyst. |
| 6 | **Coherence bin 1: DC or first non-DC?** | Unresolved with the vendor. The emitted axis is `f_k = (k-1) x 32/62`, so bin 1 is 0.00 Hz — a third convention, distinct from both readings of the format reference. `constants.py` used to assert "DC bin excluded, 0.5 to 32.0 Hz", which contradicted the formula the code runs; that claim is gone, and the behaviour is unchanged pending an answer. Tier EMP. |
| 7 | **Columns still on tier EMP** | Rhythmic-delta boolean expansions, `rda_*` value encoding (all-zero in the example recording, so binary vs probability is undetermined), and the FFT/asymmetry spectrogram bin-edge convention — whether sub-column `_k` is the bin centre or its upper edge. Read the `evidence_tier` column before relying on any of these. |
| 8 | **Rhythmicity band edges are not conventional** | Persyst hard-codes the four filter banks at **1–4, 4–9, 9–16, 16–25 Hz**. Band 2 spans conventional theta *and* low alpha; band 3 spans high alpha *and* low beta. This belongs in any methods section that reports rhythmicity by band. |
| 9 | **Timebase caveats** | Timestamps are tz-naive and therefore DST-blind: a recording crossing a daylight-saving boundary mis-measures elapsed hours by ~1 h. Pre-ROSC epochs are discarded, not labelled. |

## 7. Where things live

| | |
|---|---|
| Docs entry point | [`docs/INDEX.md`](docs/INDEX.md) |
| Per-column reference | `docs/COLUMN_MAP_V10_*.{csv,html,json}` — regenerate via `scripts/gen_column_map_v10.py` |
| Naming rules | [`docs/COLUMN_NAMING.md`](docs/COLUMN_NAMING.md); implementation in `qeeg/ingestion/column_mapper.py` |
| Template catalog | [`docs/PERSYST_V10_REFERENCE.md`](docs/PERSYST_V10_REFERENCE.md) + generated `persyst_v10_*` — regenerate via `scripts/sync_persyst_docs.py` |
| Vocabulary history | `qeeg/__version__.py` — records what each `COLUMN_SCHEMA_VERSION` changed |
| Dated audits, plans, handoffs | `docs/_project/` — development repository only; not shipped |
| Superseded templates, column crosswalks, the frozen 2026-05-15 format reference | `_archive/`, `docs/_archive/` — development repository only; not shipped, because they describe templates this pipeline can no longer read |
| Building a release tree | `python scripts/build_release.py [dest]` |

Anti-drift: `scripts/sync_persyst_docs.py --check` and the doc tests fail the
build when a generated artifact goes stale against the code or the MMX. When a
fact changes, update the canonical doc — everything else links to it.
