# Persyst Trend Panel CSV Export — Format Reference
## Template: `PedQuEST_Pennsieve_V10_research.mmx`
### Applies to: all 22 panels in the shipped template (the 5 "Research" panels share the CSV layout; clinical panels use the same layout with a smaller column subset)

> **This is not a vendor specification.** Persyst publishes no CSV layout
> document. The only mention of the export across the whole Persyst 15 help
> corpus is `/ExportCSV` in *Persyst Command Line Interface*: it names the flag
> and says nothing about column order, header rows, or sub-column contracts.
> Everything below is **reverse-engineered from real exports and from the MMX**,
> and each claim carries a "Confirmed?" marking saying how far it was verified.
> Where a row is unconfirmed, treat it as our best reading rather than a
> guarantee. For vendor statements, go to `Persyst-15-Help/`.

### Source of truth: the shipped MMX. Its catalog is serialized to `docs/persyst_v10_catalog.json` and summarized in `docs/PERSYST_V10_REFERENCE.md`.

---

## Overview

Persyst exports each trend panel as a separate CSV file. All "Research" panels in this template share the same file-level structure and column-header convention. This document describes:

1. The fixed file structure (header rows, column-ID naming)
2. The technical format for each **trend type** — how many sub-columns it exports, what each sub-column represents, and the units or value range
3. Which trend types appear in each Research panel

Trends of the same type that appear in multiple panels are documented once here. The panel inventory in §4 lists the trends per panel without repeating their technical specification.

---

## 1. File Structure

### 1.1 Metadata Rows (Rows 1–6)

Every exported CSV begins with six fixed `key,value` rows before any column headers.

| Row | Key | Example | Notes |
|-----|-----|---------|-------|
| 1 | `File` | `C:\path\to\recording.dat` | Full path to the `.dat` source file |
| 2 | `PatientName` | `Velasquez, Jorge` | Last, First (the name itself may contain a comma) |
| 3 | `PatientID` | `8675309` | String |
| 4 | `PatientBirthDate` | `05/06/2006` | MM/DD/YYYY |
| 5 | `TestDate` | `2008.11.07` | YYYY.MM.DD |
| 6 | `TestTime` | `10.23.03` | HH.MM.SS (24-hour) |

### 1.2 Column Header Rows (Rows 7–8)

**Row 7 — Trend group labels.** A properly-quoted CSV row (fields may contain commas; parse with a standards-compliant CSV reader). Each non-empty cell is the display name of the trend instrument that starts at that column position. Empty cells between two non-empty cells are "continuation" cells belonging to the preceding instrument — analogous to merged cells. This row must not be split on commas without proper quote handling.

The label format for quantitative instruments is typically:
```
<DisplayTitle>, <MeasureType>, <FreqRange>, <ChannelGroup>
```
For simpler instruments (artifact, spike, seizure, sleep) the label is a plain description string.

**Row 8 — Column identifiers.** Unquoted, comma-separated. The first two identifiers are always:

| Identifier | Description |
|------------|-------------|
| `ClockDateTime` | Wall-clock timestamp as OLE Automation date |
| `Time` | Elapsed recording time in seconds |

All remaining columns follow the pattern `I{n}_{k}`:
- `n` = instrument index (1-based, sequential within the exported panel)
- `k` = sub-column index within that instrument (1-based)

Instruments with a single output value use only `I{n}_1`. Instruments with multiple sub-columns use `I{n}_1` through `I{n}_{K}`.

### 1.3 Data Rows (Row 9 onward)

One row per **second** of recording. Values of `0` at the start of a recording are normal for trends that require a warm-up window (spectrograms, running averages); they are not true zeros. Empty fields do not appear in practice.

---

## 2. Timestamp Columns

Both timestamp columns appear in every exported panel.

| Column | Type | Description |
|--------|------|-------------|
| `ClockDateTime` | float64 | OLE Automation serial date: number of days (including fraction) since 1899-12-30. Convert in Python: `datetime(1899,12,30) + timedelta(days=v)` |
| `Time` | int | Elapsed seconds from recording start (0-indexed) |

A redundant `Time` instrument (`I{n}_1`, last in panel) is also present and repeats the elapsed-seconds value in the `ClockDateTime` format.

---

## 3. Trend Types

### 3.0 Sub-column count contract (summary)

This summary table is the **canonical sub-column-count contract** for every Persyst trend family. Detailed semantics (per-sub-column meaning, frequency-bin formulae, units, value ranges) are in §§3.1–3.29 below. Verified against the Research-panel export `1002_1.csv` (3772 columns, instruments I1–I250) on 2026-05-20.

**Fixed-cardinality families (hard-fail on mismatch when importing a new CSV):**

| Family / instrument | Sub-cols | Verified instance(s) |
|---|---:|---|
| Artifact Intensity | 3 | I1 |
| Artifact Detector | 18 | I2 |
| aEEG | 5 | I20 (L), I21 (R) |
| Seizure Detections + Notifications (combined) | 2 | I119 |
| Rhythmicity FreqPow (4 bands × 4 values) | 16 | I211–I214 |
| FFT Spectrogram | 40 | 32 instances (I187–I210, …) |
| Asymmetry Relative Spectrogram | 40 | 8 instances |
| Coherence Spectrogram | 63 | I243–I246 |
| Rhythmicity Spectrogram (sqrt-scaled, the default) | 97 | 20 instances |
| Rhythmicity Spectrogram (linear option, not used here) | 73 | — |

**Single-value families (sub-cols = 1):**

FFT_Power, FFT_PowerRatio, FFT_Edge SEF, REASI, EASI, Coherence_Avg, BSR (Suppression Ratio), Peak Envelope, Seizure Probability (continuous), Seizure Detections (binary alone), Seizure Notifications (binary alone), Seizure Events P14, SpikeDensityV1, EventDensity, Boolean indicators (LAD/LPD/LRD/RAD/RPD/RRD/SpikeRateThreshold), Rhythmic Delta indicators, SleepStages, Sleep-Wake Stage/State, ColorScaledBars, Heart Rate, TimeAvg, SumValues_Abs (Rhythmicity), Threshold (Rhythmicity), Comment.

**Recording-system-dependent families (warn-and-log on mismatch — count varies with acquisition hardware):**

| Family | Sub-cols depend on | Observed |
|---|---|---:|
| Electrode Signal Quality | # of acquisition channels in the `.dat` file (electrodes, not BP-Long pairs) | 22 |

> [!important] **Pipeline contract:** `qeeg/ingestion/subcol_validator.py` implements this table as Python code. When you update §3 (any sub-section), update `EXPECTED_SUBCOL_COUNTS` in that file to match — they must stay in lockstep. The validator runs at parse time and writes mismatches to the patient's `data_dictionary.json`.

### 3.1 Artifact Intensity
**Sub-columns: 3** | **Label pattern:** `Artifact Intensity`

Measures signal contamination from three artifact sources in the order below. Values are updated at the same 1-second rate as all other trend data.

| Sub-col | Source | Units | Range |
|---------|--------|-------|-------|
| `_1` | Muscle artifact | µV | ≥ 0; higher = more muscle noise |
| `_2` | Vertical eye movement | Probability | 0–1 |
| `_3` | Lateral eye movement | Probability | 0–1 |

---

### 3.2 Artifact Detector
**Sub-columns: 18** | **Label pattern:** `Artifact Detector`

This is essentially a matrix of 18 probabilistic classifiers the Persyst engine uses internally for its algorithms and aren’t generally useful directly.

---

### 3.3 Electrode Signal Quality
**Sub-columns: 22 (recording-system dependent)** | **Label pattern:** `Electrode Signal Quality`

Continuous signal quality estimate per **acquisition-system channel** (not per BP-Longitudinal derivation — this is a frequent point of confusion). Persyst measures quality at the raw electrode level before montaging. Values are dimensionless; **lower is better**.

| Value range | Interpretation |
|-------------|---------------|
| 0.0 | Perfect — no artifact |
| 0.0–0.5 | Acceptable |
| > 0.5 | Artifact present (channel active but noisy) |
| > 1.0 | Disconnect threshold exceeded — electrode impedance above the recording system's disconnect threshold |
| ≥ 1.2 | Disconnected / unused (threshold used by the reporting script) |

#### Sub-column count is recording-system dependent

The number of sub-columns equals the number of acquisition channels in the source `.dat` file. Confirmed counts observed in PedQuEST exports:

| Recording | Sub-col count | Composition (typical) |
|---|---|---|
| Pediatric 10-20 + EKG (POCCA/PedQuEST) | **22** | 19 standard 10-20 electrodes + EKG + 2 reference/mastoid (A1/A2, M1/M2) — exact composition is recording-system dependent |
| 18-channel BP-Long derivation export (legacy) | 18 | Listed below for reference — **not applicable when the source `.dat` has 22 channels** |

> [!important] Don't assume the 18-row table below applies to your file. Always derive the sub-col → electrode mapping from the recording's actual channel list (header row of the `.dat` file or its EDF/Persyst metadata) before publication.

#### Sub-column to Channel Mapping — legacy 18-channel BP-Longitudinal order

| Sub-col | Channel | Sub-col | Channel |
|---------|---------|---------|---------|
| `_1` | FP1-F7 | `_10` | F3-C3 |
| `_2` | F7-T7 | `_11` | C3-P3 |
| `_3` | T7-P7 | `_12` | P3-O1 |
| `_4` | P7-O1 | `_13` | FP2-F4 |
| `_5` | FP2-F8 | `_14` | F4-C4 |
| `_6` | F8-T8 | `_15` | C4-P4 |
| `_7` | T8-P8 | `_16` | P4-O2 |
| `_8` | P8-O2 | `_17` | Fz-Cz |
| `_9` | FP1-F3 | `_18` | Cz-Pz |

---

### 3.4 aEEG (Amplitude-Integrated EEG)
**Sub-columns: 5** | **Label pattern:** `aEEG, <ChannelGroup>`

Five amplitude envelope values computed over the aEEG smoothing window. Units: **µV**. Sub-columns are in the following fixed order:

| Sub-col | Value |
|---------|-------|
| `_1` | Maximum (p100 / upper envelope) |
| `_2` | Minimum (p0 / lower envelope) |
| `_3` | Median (p50) |
| `_4` | 75th percentile |
| `_5` | 25th percentile |

Available channel groups: Left Hemisphere, Right Hemisphere, All 10-20.

---

### 3.5 FFT Band Power
**Sub-columns: 1** | **Label pattern:** `FFT Power, <band> Hz, <ChannelGroup>`

Instantaneous FFT power in a named frequency band, averaged over the channel group. Computed from the same FFT engine as the FFT Spectrogram (128-pt window, 64 Hz sampling rate, 0.5 Hz resolution, 4-epoch smoothing).

Units: **uV²** (mean squared amplitude, not log-transformed).

Available frequency bands: **1–4 Hz, 4–8 Hz, 8–13 Hz, 13–20 Hz** (and the composite 1–20 Hz used by FFT Power Ratio numerators). **There is no 13–30 Hz instrument in the MMX.** Any "wide-beta" 13–30 Hz column emitted by the qEEG pipeline is a **derived** sum of spectrogram bins and must be labeled as such in the data dictionary.

Available channel groups (varies by band): All 10-20, Asym Anterior, Asym Posterior, Left/Right Anterior, Left/Right Posterior, Left/Right Hemisphere, and individual channel chains (F3C3P3, F4C4P4, F7T7P7, F8T8P8, P3P7O1, P4P8O2).

#### Running-average variants

The label prefix indicates the averaging window:
- **No prefix** — instantaneous (current epoch, ~4-second update window)
- **`Time (2 min. running ave.) <band>Hz`** — 120-second (2-minute) running average
- **`Time (64 sec running ave), FFT Power`** — 64-second running average

All variants produce a single value per channel group.

---

### 3.6 FFT Power Ratio
**Sub-columns: 1** | **Label pattern:** `FFT PowerRatio, <numerator>/<denominator> Hz, <ChannelGroup>`

Ratio of instantaneous FFT power in two frequency bands (numerator band / denominator band). Dimensionless.

Available ratios: 8-13/1-4 Hz (ADR-type), 4-8/1-4 Hz (theta/delta), 6-14/1-20 Hz (RAV-type).

Available channel groups: same as FFT Band Power (§3.5).

---

### 3.7 ADR (Alpha/Delta Ratio, Time-Averaged)
**Sub-columns: 1** | **Label pattern:** `ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz <LeftChannel> (Blue) <RightChannel> (Red), FFT PowerRatio, 8-13/1-4 Hz, <Side>`

2-minute running average of the 8–13 / 1–4 Hz FFT Power Ratio. Displayed as a paired left/right trend, exported as individual single-column values. Dimensionless. Higher values indicate more alpha relative to delta.

Available channel groups: Left/Right Anterior, Left/Right Hemisphere, Left/Right Posterior, F3C3P3/F4C4P4, F7T7P7/F8T8P8, P3P7O1/P4P8O2.

---

### 3.8 RAV (Relative Alpha Variability, Time-Averaged)
**Sub-columns: 1** | **Label pattern:** `RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz <ChannelGroup>, FFT PowerRatio, 6-14/1-20 Hz, <ChannelGroup>`

2-minute running average of the 6–14 / 1–20 Hz FFT Power Ratio. Dimensionless.

Available channel groups: Left/Right Anterior, Left/Right Hemisphere, Left/Right Posterior, F3C3P3, F4C4P4, F7T7P7, F8T8P8, P3P7O1, P4P8O2.

---

### 3.9 Time-Averaged Trend (TimeAvg)
**Sub-columns: 1** | **Label pattern:** `Time Avg <0,N> [<SourceTrend>]`

A time-windowed average of an underlying trend. The label encodes the averaging window as `<minOffset,windowSeconds>`, where offset 0 means the window ends at the current time.

| Label component | Meaning |
|-----------------|---------|
| `<0,64>` | Running average over the past 64 seconds |
| `<0,120>` | Running average over the past 120 seconds (2 minutes) |


The value is a scalar of the same type and units as the source trend. Source trends in this template are FFT Band Power (uV²) and FFT Power Ratio (dimensionless).

Used in panels: Research-TimeAverages, Research-LimitedElectrodes.

---

### 3.10 Asymmetry — EASI (Absolute Index)
**Sub-columns: 1** | **Label pattern:** `Asymmetry, Absolute Index (EASI), <band> Hz, <ChannelGroup>`

EEG Asymmetry Spectral Index (absolute). Measures the magnitude of spectral asymmetry between hemispheres without regard to direction.

| Units | Range | Interpretation |
|-------|-------|----------------|
| % | 0–100 | 0 = perfect symmetry; higher = greater asymmetry |

Available bands: 0–20 Hz.

---

### 3.11 Asymmetry — REASI (Relative Index)
**Sub-columns: 1** | **Label pattern:** `Asymmetry, Relative Index (REASI), <band> Hz, <ChannelGroup>`

Relative EEG Asymmetry Spectral Index. Encodes both magnitude and direction of spectral asymmetry.

| Units | Range | Interpretation |
|-------|-------|----------------|
| % | −100 to +100 | Positive = right > left; negative = left > right; 0 = symmetric |

Available bands: 0–5 Hz, 4–8 Hz, 6–14 Hz, 0–20 Hz.

Available channel groups: Asym Hemi (full hemisphere), Asym Anterior, Asym Posterior, Asym Parasagittal, Asym Temporal.

---

### 3.12 FFT Spectrogram
**Sub-columns: 40** | **Label pattern:** `FFT Spectrogram, <ChannelGroup>`

Per-frequency-bin power spectral density, one row per second. Computed with the FFT engine settings shown below.

#### FFT Engine Parameters (from `EngineFFT`)

| Parameter | Value |
|-----------|-------|
| Sampling rate | 64 Hz |
| Points per window | 128 |
| Windows per epoch | 4 |
| Window duration | 2 seconds |
| Overlap windows | Yes |
| Epoch duration | 4 seconds |
| Frequency resolution | 0.5 Hz |
| Smoothing | 3 epochs |
| Display range | 0–20 Hz |
| Exported bins | 40 |

#### Frequency Axis

Each sub-column `_k` (k = 1…40) represents a frequency bin centered at **k × 0.5 Hz**:

| Sub-col | Center frequency |
|---------|-----------------|
| `_1` | 0.5 Hz |
| `_2` | 1.0 Hz |
| `_3` | 1.5 Hz |
| … | … |
| `_20` | 10.0 Hz |
| … | … |
| `_40` | 20.0 Hz |

#### Units

Values are stored as **√(power)** (square root of µV²/Hz), i.e., amplitude spectral density in µV/√Hz. This transformation improves dynamic range for the limited color palette of the spectrogram display. To recover power spectral density in µV²/Hz, square each value.

#### Available Derivations

All 10-20 average, C3-P3, C4-P4, CZ-PZ, F3-C3, F4-C4, F7-T3, F8-T4, FP1-F3, FP1-F7, FP2-F4, FP2-F8, Fz-Cz, Left Anterior, Left Hemisphere, Left Posterior, P3-O1, P4-O2, Right Anterior, Right Hemisphere, Right Posterior, T3-T5, T4-T6, T5-O1, T6-O2.

---

### 3.13 Asymmetry Relative Spectrogram
**Sub-columns: 40** | **Label pattern:** `Asymmetry, Relative Spectrogram <ChannelPair or Group>`

Per-frequency REASI (see §3.11) computed at each FFT bin. Uses the same 40-bin, 0.5 Hz/bin frequency axis as the FFT Spectrogram (§3.12), so sub-column `_k` = k × 0.5 Hz.

| Units | Range |
|-------|-------|
| % | −100 to +100 per frequency bin |

Available derivations: F4C4P4 vs F3C3P3, F8T4T6 vs F7T7P7, P4T6O2 vs P3P7O1, Asym Anterior, Asym Hemi, Asym Parasagittal, Asym Posterior, Asym Temporal, F3C3P3, F7T7P7, P3P7O1.

---

### 3.14 Coherence Average
**Sub-columns: 1** | **Label pattern:** `Coherence_Avg 0-32 <Pair>, <band>, <Pair>`

Mean squared coherence averaged over 0–32 Hz between a left-hemisphere and right-hemisphere channel pair.

| Units | Range |
|-------|-------|
| Dimensionless | 0–1 (0 = no coherence, 1 = perfect coherence) |

Available channel pairs: C3-P3 × C4-P4, F3-C3 × F4-C4, P3-O1 × P4-O2, T3-T5 × T4-T6, T5-O1 × T6-O2.

---

### 3.15 Coherence Spectrogram
**Sub-columns: 63** | **Label pattern:** `Coherence_Spectrogram 0-32 <Pair>, <Pair>`

Per-frequency squared coherence, computed over 0–32 Hz. 63 bins at equal linear spacing.

#### Frequency Axis

Sub-column `_k` (k = 1…63) represents frequency = **(k − 1) × (32/62)** Hz ≈ **(k − 1) × 0.516 Hz**:

| Sub-col | Approx. frequency |
|---------|------------------|
| `_1` | 0.0 Hz (DC) |
| `_2` | 0.516 Hz |
| `_32` | 16.0 Hz |
| `_63` | 32.0 Hz |

| Units | Range |
|-------|-------|
| Dimensionless | 0–1 per bin |

Available channel pairs: same as Coherence Average (§3.14).

---

### 3.16 Heart Rate
**Sub-columns: 1** | **Label pattern:** `Heart Rate`

Instantaneous heart rate derived from the EKG channel.

| Units | Typical range |
|-------|--------------|
| BPM | 40–200 |

The panel may contain two Heart Rate instruments using different EKG channel engines. If both are present, the second instrument may be all-zero if its engine's channel is not available in the recording.

---

### 3.17 Peak Envelope
**Sub-columns: 1** | **Label pattern:** `PeakEnvelope, <band> Hz, <ChannelGroup>`

Peak-to-peak amplitude envelope of the EEG filtered to the specified band.

| Units | Range |
|-------|-------|
| µV | ≥ 0 |

Available band: 2–20 Hz.

Available channel groups: All 10-20, Left/Right Anterior, Left/Right Hemisphere, Left/Right Posterior.

---

### 3.18 Suppression Ratio
**Sub-columns: 1** | **Label pattern:** `Suppression Ratio, <ChannelGroup>`

Fraction of the current epoch in which EEG amplitude is below the burst-suppression threshold.

| Units | Range |
|-------|-------|
| % | 0–100 |

Available channel groups: All 10-20, Left/Right Hemisphere, Left/Right Anterior, Left/Right Posterior.

---

### 3.19 Spectral Edge Frequency (SEF)
**Sub-columns: 1** | **Label pattern:** `SEF<percentile>, <ChannelGroup>` or `SEF <percentile> <Region>, <ChannelGroup>`

Frequency below which the specified percentage of total spectral power (0–32 Hz) is contained.

| Units | Range |
|-------|-------|
| Hz | 0–32 |

Available percentiles: SEF50, SEF75, SEF90, SEF95. Available channel groups: All 10-20, Left/Right Hemisphere, Left/Right Anterior, Left/Right Posterior, Asym Anterior, Asym Posterior.

---

### 3.20 Boolean Lateralized Discharge Indicators
**Sub-columns: 1 each** | **Label patterns:** `Boolean LAD+`, `Boolean LPD+`, `Boolean LRD+`, `Boolean RAD+`, `Boolean RPD+`, `Boolean RRD+`

One binary indicator per discharge type. Active (= 1) when the underlying detector's combined frequency + power thresholds are both met simultaneously.

| Instrument | Discharge |
|-----------|-----------|
| Boolean LAD+ | Left Anterior Discharge |
| Boolean LPD+ | Left Posterior Discharge |
| Boolean LRD+ | Left Rhythmic Discharge |
| Boolean RAD+ | Right Anterior Discharge |
| Boolean RPD+ | Right Posterior Discharge |
| Boolean RRD+ | Right Rhythmic Discharge |

| Value | Meaning |
|-------|---------|
| `1` | Both frequency and power thresholds exceeded |
| `0` | Threshold not met |

---

### 3.21 Rhythmic Delta Indicators
**Sub-columns: 1 each** | **Label pattern:** `Rhythmic delta indicator (blue=left, red=right, green=gen)`

Three instruments (left, right, generalized) display the state of the rhythmic delta pattern. The color coding is a display-only property.

**[Encoding not confirmed from available data — all three values were 0 throughout the example recording. Likely binary or probability.]**

---

### 3.22 Seizure Detection
**Sub-columns: 1 (or 2)** | **Label patterns below**

| Instrument | Cols | Description | Values |
|-----------|------|-------------|--------|
| `Seizure Detections (red) and Notifications (gray)` | 2 | Col `_1` = seizure detections; col `_2` = seizure notifications | Binary: 0 or 1 |
| `Seizure Notifications (P14)` | 1 | Notification-level output of the P14 seizure detector | Binary: 0 or 1 |
| `Seizure probability (black) and detections (red; hides probability)` | 1 | Continuous probability output; when a detection occurs the probability display is suppressed and replaced by a detection marker | Float 0–1 (probability) or binary detection; see note |
| `Time, Seizure probability (…)` | 1 | Time-registered version of seizure probability | Same as above |

**Detection vs. probability:** Seizure *detections* are binary (0 or 1). Seizure *probability* is a continuous value 0–1. Some instruments export the probability continuously; others switch between probability and a detection flag depending on the display mode. Check the instrument label to determine which mode is active.

No seizures were present in the example recording; all seizure columns were 0.

---

### 3.23 Sleep Staging
**Sub-columns: 1 each** | **Label patterns:** `SleepStages`, `Sleep-Wake Stage (…)`, `Sleep-Wake State (…)`

Sleep stage is computed in 30-second epochs and held constant for the duration of each epoch. The same underlying stage is output through multiple instruments with different display rendering:

| Instrument | Description |
|-----------|-------------|
| `SleepStages` | Primary histogram value (see code table below) |
| `Sleep-Wake Stage (yellow=wake; …)` | Stage detail with color-coded display (6 instances) |
| `Sleep-Wake State (yellow=wake; blue=sleep; …)` | Binary wake/sleep state |

#### Sleep Stage Code Table

| Code | Stage |
|------|-------|
| `5` | Wake |
| `4` | REM |
| `3` | N1 |
| `2` | N2 |
| `1` | N3 |
| `0` | Indeterminate (unscored) |

The `Sleep-Wake State` instrument (binary) uses `1` for sleep and `0` for wake, with indeterminate states mapped to one or the other depending on classifier confidence.

The six `Sleep-Wake Stage` instruments each appear to output the same numeric code (§ above); the multiplicity reflects separate display-row instances in the panel layout rather than distinct output values.

---

### 3.24 Spike Detection
**Sub-columns: 1 each** | **Multiple instruments**

All spike instruments are updated every second. "Count per sec" values reflect spikes detected within that second's 1-Hz epoch; "count per 10 sec" values reflect a 10-second sliding window count.

| Instrument | Units | Notes |
|-----------|-------|-------|
| `Spike Burst Detections` | Binary (0/1) | Simultaneous multi-focal spike burst |
| `Spike Detections generalized (count per sec)` | Integer | Count of generalized spike events per second |
| `Spike Detections generalized (count per 10s)` | Integer | Count over a 10-second window |
| `Spike Detections left hemisphere (count per sec)` | Integer | Left-focal spikes per second |
| `Spike Detections left hemisphere (count per 10 sec)` | Integer | Left-focal spikes per 10-second window |
| `Spike Detections right hemisphere (count per sec)` | Integer | Right-focal spikes per second |
| `Spike Detections right hemisphere (count per 10 sec)` | Integer | Right-focal spikes per 10-second window |
| `Spike Detections vertex (count per sec)` | Integer | Vertex (Fz/Cz/Pz) spikes per second |
| `Spike Detections, all foci (count per sec)` | Integer | Sum across all focal detectors per second |

#### Spike Rate Threshold Instruments

Binary flag indicating whether the 10-second spike rate meets or exceeds 3 spikes/10 sec.

| Instrument | Threshold source | Value |
|-----------|-----------------|-------|
| `Spike RateThreshold, left hemisphere >=3 per 10 sec` | Left hemi count/10s | 1 if ≥ 3, else 0 |
| `Spike Rate Threshold, right hemisphere >=3 per 10 sec` | Right hemi count/10s | 1 if ≥ 3, else 0 |
| `Spike RateThreshold, generalized >=3 per 10 sec` | Generalized count/10s | 1 if ≥ 3, else 0 |

#### Lateralized High-Rate Spike Instruments

Four overlapping display instruments that each encode one lateralization state when the 10-second spike rate reaches ≥ 3/10 sec. They are ordered in the panel (and thus in the CSV) as follows:

| Order | Instrument label | Condition encoded |
|-------|-----------------|-------------------|
| 1st | `Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R)` | **Left hemisphere only** (left ≥ 3/10s AND right < 3/10s) |
| 2nd | `Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R)` | **Right hemisphere only** (right ≥ 3/10s AND left < 3/10s) |
| 3rd | `Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R), green=generalized)` | **Bilateral** (both left AND right ≥ 3/10s) |
| 4th | `Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R), green=generalized)` | **Generalized** (generalized spike count ≥ 3/10s) |

The four instruments share the same two label strings (one without "green=generalized", one with it), so the CSV column identifier `I{n}_1` is the only way to distinguish them by position. All four were 0 throughout the example recording; **binary (0/1) encoding is expected** based on the threshold-detection design, but exact value behavior under simultaneous conditions is not confirmed from data.

---

### 3.25 Rhythmicity Spectrogram — SumValues
**Sub-columns: 1** | **Label pattern:** `SumValues <Region> delta <freq|power>, Rhythmicity Spectrogram FreqPow <Region>, 1 - 25 Hz, <ChannelGroup>`

Scalar summaries of the Rhythmicity Spectrogram within the delta band (1–4 Hz), extracted from the FreqPow spectrogram (§3.27). Two instruments per channel group:

| Instrument suffix | Value | Units |
|-------------------|-------|-------|
| `delta freq` | Peak rhythmic frequency within the delta band | Hz |
| `delta power` | Integrated rhythmic power within the delta band | uV/Hz (see §3.27) |

Available channel groups: Left Anterior (LA), Left Posterior (LP), Right Anterior (RA), Right Posterior (RP).

---

### 3.26 Rhythmicity Spectrogram — Threshold
**Sub-columns: 1** | **Label pattern:** `Threshold <Region>>=<threshold>, SumValues <Region> delta <freq|power>, [Rhythmicity Spectrogram …]`

Binary (0/1) flag indicating whether the corresponding SumValues metric (§3.25) meets or exceeds a threshold.

| Threshold | Default value | Source metric |
|-----------|--------------|---------------|
| `>=1.1 Hz` | 1.1 Hz | Delta peak frequency |
| `>=5 uV/Hz` | 5 µV/Hz | Delta band power |

Four pairs of thresholds (freq and power) for each of four channel groups (LA, LP, RA, RP) = 8 threshold instruments total.

Example: `Threshold LAD>=1.1Hz` = 1 means the Left Anterior Rhythmic Delta peak frequency is ≥ 1.1 Hz.

---

### 3.27 Rhythmicity Spectrogram — FreqPow
**Sub-columns: 16** | **Label pattern:** `Rhythmicity Spectrogram FreqPow <Region>, 1 - 25 Hz, <ChannelGroup>`

A combined per-epoch summary of rhythmic activity. Four separate instruments are exported, one per anatomical quadrant (LA, LP, RA, RP), matching the four Rhythmicity Spectrogram channel groups. Each instrument has **16 sub-columns structured as 4 frequency bands × 4 values per band**.

**Note on sub-column anatomy:** The LA/LP/RA/RP labels in the instrument names identify *which quadrant the instrument covers*, not the sub-column layout. Each instrument's 16 sub-columns are all for its own quadrant, organized by frequency band. This was confirmed by verifying that sub-column `_1` of each instrument matches that quadrant's SumValues delta frequency (§3.25) — values differ between quadrants and are independent of one another.

**Frequency band layout:**

| Cols | Band | Approx. range |
|------|------|---------------|
| `_1`–`_4` | Delta | ~1–4 Hz |
| `_5`–`_8` | Theta | ~4–8 Hz |
| `_9`–`_12` | Alpha | ~8–13 Hz |
| `_13`–`_16` | Beta | ~13–25 Hz |

Within each 4-column block, positions 1 and 3 are confirmed; positions 2 and 4 are not:

| Position within block | Value | Units | Confirmed? |
|----------------------|-------|-------|------------|
| 1 (e.g. `_1`, `_5`, `_9`, `_13`) | Peak rhythmic frequency in this band | Hz | Yes — matches SumValues delta freq (§3.25) for delta block |
| 2 (e.g. `_2`, `_6`, `_10`, `_14`) | Not confirmed | — | No |
| 3 (e.g. `_3`, `_7`, `_11`, `_15`) | Integrated rhythmic power in this band | same units as §3.28 | Yes — matches SumValues delta power (§3.25) for delta block |
| 4 (e.g. `_4`, `_8`, `_12`, `_16`) | Not confirmed | — | No |

Available channel groups: Left Anterior (LA), Left Posterior (LP), Right Anterior (RA), Right Posterior (RP).

---

### 3.28 Rhythmicity Spectrogram (Full)
**Sub-columns: 97** | **Label pattern:** `Rhythmicity Spectrogram, <ChannelGroup>`

Full per-frequency-bin rhythmicity power, one row per update interval (not necessarily every second — the spectrogram is updated on a longer computation window; rows with no update are zero). Rows without new data contain all zeros.

#### Frequency Axis — Square-Root Scaled

The frequency axis is scaled with a square-root transformation by default ("Scale Freq axis with Sqrt" in the Rhythmicity Spectrogram settings), providing better resolution in the delta range.

Sub-column `_k` (k = 1…97) represents frequency:

$$f_k = \left(1 + \frac{k-1}{24}\right)^2 \text{ Hz}$$

Equivalently: `f_k = (1 + (k-1)/24)^2`

| Sub-col | Frequency |
|---------|----------|
| `_1` | 1.00 Hz |
| `_2` | 1.09 Hz |
| `_5` | 1.36 Hz |
| `_13` | 2.24 Hz |
| `_25` | 4.00 Hz |
| `_37` | 6.25 Hz |
| `_49` | 9.00 Hz |
| `_61` | 12.25 Hz |
| `_73` | 16.00 Hz |
| `_85` | 20.25 Hz |
| `_97` | 25.00 Hz |

For comparison: when the Sqrt scaling option is **disabled**, the same spectrogram exports **73 bins** with a linear frequency axis:
- Sub-col `_k`: f_k = 1 + (k−1)/3 Hz (spacing = 1/3 Hz, range 1–25 Hz)

#### Units

Rhythmicity power values represent the rhythmic component's spectral amplitude. Units are consistent with the FreqPow spectrogram power column (§3.27).

#### Available Channel Groups / Derivations

All 10-20, C3-P3, C4-P4, CZ-PZ, F3-C3, F4-C4, F7-T3, F8-T4, FP1-F3, FP1-F7, FP2-F4, FP2-F8, Fz-Cz, Left Hemisphere, P3-O1, P4-O2, Right Hemisphere, T3-T5, T4-T6, T5-O1, T6-O2.

---

### 3.29 Comment
**Sub-columns: 1** | **Label:** `Comment`

Free-text annotation string entered in Persyst's timeline comment tool. Empty string when no comment is present at that second. Appears once per panel at the end of the column list.

---

## 4. Panel Inventory

The template contains **22 panels total**: 17 clinical/QC panels plus 5 "Research" panels. All exports share the file structure (§1). The five Research panels are the primary research export targets and are documented in detail below; the 17 clinical panels use the same trend types and are listed in §4.6 for completeness.

The five Research panels each may be exported independently; each export has the same file structure (§1) but contains only the trend types listed for that panel.

### 4.1 Research

The comprehensive panel (318 instruments). Contains all trend types described in §3, covering all available channel groups and derivations. Includes several instances of the same trend type on different channel groups as separate display rows; these appear as separate instruments in the CSV.

Notable content:
- All FFT Spectrogram derivations (25 channels)
- All Rhythmicity Spectrogram derivations (21 channels)
- All Coherence Spectrogram pairs (5 pairs)
- All Asymmetry Relative Spectrogram groups (8 groups)
- Full spike, seizure, sleep, aEEG, and asymmetry trend suites

### 4.2 Research-Trends

The trends-only panel (190 instruments). No spectrogram sub-column data. Contains:
- aEEG (All 10-20, Left Hemisphere, Right Hemisphere)
- Artifact Detector, Artifact Intensity, Electrode Signal Quality
- Asymmetry Index (EASI and REASI, all bands and regions)
- Asymmetry Relative Spectrogram (all 8 groups) — *note: this is a multi-column trend included despite "Trends" naming*
- Boolean LAD/LPD/LRD/RAD/RPD/RRD
- Coherence Average (5 pairs)
- FFT Band Power (all bands, all channel groups)
- FFT Power Ratio (all ratios, all channel groups)
- Heart Rate (2 instances)
- Peak Envelope (all channel groups)
- RAV (running average, all channel groups)
- Rhythmic Delta Indicators (3)
- SEF (50/75/90/95, all channel groups)
- Seizure Detection, Probability, Notifications
- Sleep Staging (7 instruments)
- Spike Detection suite (counts, thresholds, lateral indicators)
- Rhythmicity SumValues and Threshold instruments
- Suppression Ratio (all channel groups)
- Comment, Time

### 4.3 Research-Spectrograms

The spectrograms panel (87 instruments). Contains multi-column spectral data:
- Artifact Detector, Artifact Intensity, Electrode Signal Quality
- Asymmetry Relative Spectrogram (8 groups × 40 bins)
- Coherence Spectrogram (5 pairs × 63 bins)
- FFT Spectrogram (25 derivations × 40 bins)
- Rhythmicity Spectrogram FreqPow (4 channel groups × 16 cols)
- Rhythmicity Spectrogram full (21 derivations × 97 bins)
- Seizure Detection, Probability, Notifications
- Spike Detection suite
- Comment, Time

### 4.4 Research-TimeAverages

Time-averaged scalar trends (35 instruments) Contains **no spectrogram data**. All instruments are of the `Time Avg <0,N> [SourceTrend]` type (§3.9).

**Only two window sizes are present:** `<0,64>` (16 instruments) and `<0,120>` (36). There is no 30-minute (`<0,1800>`) layer. Read the window from the MMX instrument name, never the CSV display label — Persyst does not rewrite the label when the underlying window changes. 

**2-minute (120-second) averages:**
- FFT Power Ratio 8-13/1-4 Hz: Left/Right Anterior, Left/Right Hemisphere, Left/Right Posterior
- FFT Power 13-20 Hz: Left Hemisphere, Right Hemisphere, All 10-20 
- FFT Power 1-4 Hz: Left Hemisphere, Right Hemisphere, All 10-20
- FFT Power 4-8 Hz: Left Hemisphere, Right Hemisphere, All 10-20
- FFT Power 8-13 Hz: Left Hemisphere, Right Hemisphere, All 10-20

**64-second averages:**
- FFT Power 13-20 Hz: Left/Right Anterior, Left/Right Posterior  
- FFT Power 1-4 Hz: Left/Right Anterior, Left/Right Posterior
- FFT Power 4-8 Hz: Left/Right Anterior, Left/Right Posterior
- FFT Power 8-13 Hz: Left/Right Anterior, Left/Right Posterior  

### 4.5 Research-LimitedElectrodes

Individual electrode-chain trends (33 instruments). Designed for recordings where only a limited electrode set is available (e.g., longitudinal chains only). Contains:

**Instantaneous FFT Power Ratios:**
- 4-8/1-4 Hz: F3C3P3, F4C4P4, F7T7P7, F8T8P8, P3P7O1, P4P8O2
- 6-14/1-20 Hz: same 6 chains
- 8-13/1-4 Hz: same 6 chains

**Asymmetry Relative Spectrogram (40-bin):** F3C3P3 vs F4C4P4, F7T7P7 vs F8T8P8, P3P7O1 vs P4P8O2

**2-minute Time-Averaged FFT Power Ratios:**
- 8-13/1-4 Hz: F3C3P3, F4C4P4, F7T7P7, F8T8P8, P3P7O1, P4P8O2
- 6-14/1-20 Hz: same 6 chains

### 4.6 Clinical / QC Panels

The MMX defines 17 clinical and drill-down panels in addition to the 5 Research panels. They use the same CSV file structure but contain a smaller, panel-specific subset of instruments. Refer to `docs/persyst_v10_panel_index.md` for the per-row index.

| # | Panel | Slots | Purpose |
|---:|---|---:|---|
| 1 | SignalQuality | 2 | Artifact Intensity + Electrode Signal Quality overlay |
| 2 | Comprehensive | 21 | Clinical overview (seizure, spikes, FFT, asymmetry, aEEG, BSR, EKG) |
| 3 | aEEG | 13 | aEEG + seizure + regional EventDensity |
| 4 | aEEG Sleep-Wake | 14 | aEEG with sleep-stage `ColorScaledBars` row |
| 5 | Asymmetry | 9 | REASI per region + asymmetry spectrograms |
| 6 | Alpha-Delta Ratios (Quadrant) | 11 | ADR TimeAvg by quadrant |
| 7 | Suppression Ratio | 10 | BSR per region + aEEG + rhythmicity |
| 8 | Rhythmicity by Channel | 18 | 18 per-channel rhythmicity spectrograms |
| 9 | Peak Envelope | 13 | PE 2–20 Hz per hemisphere |
| 10 | Power by Frequency Band | 10 | 2-min TimeAvg band power by hemisphere |
| 11 | RhythmicDeltaDetails | 5 | L/R anterior+posterior rhythmicity boolean detail |
| 12 | SpikeDetails | 12 | Spike density + EventDensity per laterality |
| 13 | Heart Rate | 8 | EKG + HR + seizure/rhythmicity context |
| 14 | Relative Alpha Variability (Quadrant) | 11 | RAV TimeAvg by quadrant |
| 15 | Relative Alpha Variability (RAV) | 11 | RAV — full set incl. asymmetry spectrograms |
| 16 | Alpha Delta Ratios (ADR) | 11 | ADR — full set incl. asymmetry spectrograms |
| 17 | SEF and SR | 15 | SEF50/75/90/95 (12 instruments) + 3 BSR |

---

## 5. Remaining Open Items

| # | Topic | Details |
|---|-------|---------|
| 1 | **Rhythmicity FreqPow sub-cols 2 & 4** | Positions 2 and 4 in each 4-tuple (§3.27) are unconfirmed. Likely peak power at that frequency and a quality/bandwidth measure, but requires Persyst documentation or user confirmation. |
| 2 | **Rhythmic delta indicator encoding** | §3.21: values were all 0 in example recording. Confirm whether these are binary (0/1), probability (0–1), or categorical. |
| 3 | **Sleep-Wake Stage (6 instances)** | §3.23: whether the 6 `Sleep-Wake Stage` instruments all export the same stage code, or whether different instances represent different algorithm outputs or confidence scores. |
| 4 | **Coherence Spectrogram bin 1** | §3.15: confirm whether sub-col `_1` represents 0 Hz (DC) or the first non-DC bin (~0.5 Hz). |
| 5 | **Artifact Detector channel order** | §3.2 (Artifact Detector, 18 channels): the sub-column to channel mapping is presumed to follow BP-Longitudinal montage order (same as §3.3) but has not been explicitly confirmed. |
| 6 | **Seizure probability vs. detection in shared instrument** | §3.22: for instruments labeled "Seizure probability (black) and detections (red; hides probability)," confirm whether the CSV value is always probability (0–1) or switches to a binary flag upon detection. |

---

## Appendix A: Frequency Bin Reference Tables

### A.1 FFT Spectrogram — 40 Bins (0.5 Hz resolution, 0–20 Hz)

| Bin | Freq (Hz) | Bin | Freq (Hz) | Bin | Freq (Hz) | Bin | Freq (Hz) |
|-----|-----------|-----|-----------|-----|-----------|-----|-----------|
| 1 | 0.5 | 11 | 5.5 | 21 | 10.5 | 31 | 15.5 |
| 2 | 1.0 | 12 | 6.0 | 22 | 11.0 | 32 | 16.0 |
| 3 | 1.5 | 13 | 6.5 | 23 | 11.5 | 33 | 16.5 |
| 4 | 2.0 | 14 | 7.0 | 24 | 12.0 | 34 | 17.0 |
| 5 | 2.5 | 15 | 7.5 | 25 | 12.5 | 35 | 17.5 |
| 6 | 3.0 | 16 | 8.0 | 26 | 13.0 | 36 | 18.0 |
| 7 | 3.5 | 17 | 8.5 | 27 | 13.5 | 37 | 18.5 |
| 8 | 4.0 | 18 | 9.0 | 28 | 14.0 | 38 | 19.0 |
| 9 | 4.5 | 19 | 9.5 | 29 | 14.5 | 39 | 19.5 |
| 10 | 5.0 | 20 | 10.0 | 30 | 15.0 | 40 | 20.0 |

### A.2 Rhythmicity Spectrogram — 97 Bins (sqrt-scaled, 1–25 Hz)

Formula: `f_k = (1 + (k-1)/24)²` Hz

| Bin | Freq (Hz) | Bin | Freq (Hz) | Bin | Freq (Hz) | Bin | Freq (Hz) |
|-----|-----------|-----|-----------|-----|-----------|-----|-----------|
| 1 | 1.000 | 26 | 4.168 | 51 | 9.507 | 76 | 17.016 |
| 2 | 1.085 | 27 | 4.340 | 52 | 9.766 | 77 | 17.361 |
| 3 | 1.174 | 28 | 4.516 | 53 | 10.028 | 78 | 17.710 |
| 4 | 1.266 | 29 | 4.694 | 54 | 10.293 | 79 | 18.062 |
| 5 | 1.361 | 30 | 4.877 | 55 | 10.562 | 80 | 18.418 |
| 6 | 1.460 | 31 | 5.062 | 56 | 10.835 | 81 | 18.778 |
| 7 | 1.562 | 32 | 5.252 | 57 | 11.111 | 82 | 19.141 |
| 8 | 1.668 | 33 | 5.444 | 58 | 11.391 | 83 | 19.507 |
| 9 | 1.778 | 34 | 5.641 | 59 | 11.674 | 84 | 19.877 |
| 10 | 1.891 | 35 | 5.840 | 60 | 11.960 | 85 | 20.250 |
| 11 | 2.007 | 36 | 6.043 | 61 | 12.250 | 86 | 20.627 |
| 12 | 2.127 | 37 | 6.250 | 62 | 12.543 | 87 | 21.007 |
| 13 | 2.250 | 38 | 6.460 | 63 | 12.840 | 88 | 21.391 |
| 14 | 2.377 | 39 | 6.674 | 64 | 13.141 | 89 | 21.778 |
| 15 | 2.507 | 40 | 6.891 | 65 | 13.444 | 90 | 22.168 |
| 16 | 2.641 | 41 | 7.111 | 66 | 13.752 | 91 | 22.562 |
| 17 | 2.778 | 42 | 7.335 | 67 | 14.062 | 92 | 22.960 |
| 18 | 2.918 | 43 | 7.562 | 68 | 14.377 | 93 | 23.361 |
| 19 | 3.062 | 44 | 7.793 | 69 | 14.694 | 94 | 23.766 |
| 20 | 3.210 | 45 | 8.028 | 70 | 15.016 | 95 | 24.174 |
| 21 | 3.361 | 46 | 8.266 | 71 | 15.340 | 96 | 24.585 |
| 22 | 3.516 | 47 | 8.507 | 72 | 15.668 | 97 | 25.000 |
| 23 | 3.674 | 48 | 8.752 | 73 | 16.000 | | |
| 24 | 3.835 | 49 | 9.000 | 74 | 16.335 | | |
| 25 | 4.000 | 50 | 9.252 | 75 | 16.674 | | |

### A.3 Coherence Spectrogram — 63 Bins (linear, 0–32 Hz)

Formula: `f_k = (k-1) × (32/62)` Hz ≈ `(k-1) × 0.516` Hz

| Bin 1 | Bin 32 | Bin 63 |
|-------|--------|--------|
| 0.0 Hz | 16.0 Hz | 32.0 Hz |

### A.4 Rhythmicity Spectrogram (Linear variant) — 73 Bins (1–25 Hz)

Formula: `f_k = 1 + (k−1)/3` Hz (spacing = 0.333 Hz)

| Bin 1 | Bin 37 | Bin 73 |
|-------|--------|--------|
| 1.0 Hz | 13.0 Hz | 25.0 Hz |

---

*Document generated 2026-05-15 from direct analysis of exported CSV files and `PedQuEST_Pennsieve_V7_research.mmx`.*
*Derived from panels: Research, Research-Trends, Research-Spectrograms (exported); Research-TimeAverages, Research-LimitedElectrodes (from MMX only).*
