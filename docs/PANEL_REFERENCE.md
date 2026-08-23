---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# qEEG Panel Reference — What Each Trend Plots

Source of truth for every panel and sub-chart the rebuilt qEEG dashboard displays. Mirrors `Ref Files/Trend panels.md` (the authoritative Persyst XML spec) and includes the backend column each trace draws from.

> **Export-only families:** non-lateralized **Anterior/Posterior** channel power (`fft_{band}_anterior`, `aeeg_anterior_*`, `suppression_anterior`, `sef_95_anterior`, `peak_envelope_anterior`) and **relative band power** (`rel_{band}_{location}`) flow through ingestion and **exports** (data dictionary, Parquet/CSV) but are **not** surfaced as dashboard panels — no sub-charts for them here. See `PERSYST_V10_REFERENCE.md`. A relative-power panel and an Anterior/Posterior regional panel are tracked frontend follow-ups.

**Overlap convention**: if a row's `Overlap` = 1, the trace is drawn on the **same sub-chart** as the prior row (e.g. aEEG Left blue + aEEG Right red → purple where they overlap). `Overlap` = 0 means a new sub-chart.

**Channel convention**: **"All 10-20" = whole brain** (average across every 10-20 electrode). Any trend whose Persyst instrument reads `... All 10-20_avg` is a whole-brain value. Applies to BSR, SEF, and any other family. Backend slug is `all` (not `all_1020`) for readability — `sef_95_all`, `suppression_all`, etc.

**Colour key** (used consistently across every hemispheric pair):
- **Blue** = Left; **Red** = Right; **Purple** = overlap region (L+R both active); **Green** = Generalized / EMG / Alpha band; **Violet** = Delta band; **Cyan** = Theta band; **Amber** = Beta band / left-only spikes; **Magenta** = right-only spikes.

---

## Panel 1 — Comprehensive

Full clinical overview.

| # | Sub-chart | Render | Overlap | Backend source | Notes |
|---|---|---|---|---|---|
| 1 | Artifact Intensity | 3-trace line | 0 | `artifact_intensity_{emg, eye_vertical, eye_horizontal}` | EMG green, eye-V blue, eye-H red |
| 2 | Seizure Probability (P14) | Filled area 0–1 | 0 | `seizure_probability_p14` | Red fill, dashed reference at 0.5 |
| 3 | P14 Detections | Ticks overlay | 1 | `seizure_detection_p14` | Overlays row 2 |
| 4 | Spike Density | 3-trace line | 0 | `spike_{left, right, generalized}_per_sec` | L blue, R red, Gen green |
| 5 | Spikes — Left only | Boolean strip | 0 | derived (L ≥ 1.5/sec) AND NOT (R ≥ 1.5/sec) | amber |
| 6 | Spikes — Right only | Boolean strip | 1 | derived | magenta |
| 7 | Spikes — Bilateral | Boolean strip | 1 | derived (L AND R ≥ 1.5/sec) | red |
| 8 | Spikes — Generalized | Boolean strip | 1 | derived from `spike_generalized_per_sec` | green |
| 9 | Rhythmicity — L only | Boolean strip | 0 | **placeholder** — requires `SumValues_Abs_*` not produced by pipeline |
| 10 | Rhythmicity — Bilateral | Boolean strip | 1 | **placeholder** | |
| 11 | Rhythmicity — R only | Boolean strip | 1 | **placeholder** | |
| 12 | Rhythmicity Spectrogram — Left | Canvas heatmap | 0 | `/spectrogram/rhythmicity` filtered to Left Hemisphere | 1–25 Hz, 97 bins |
| 13 | Rhythmicity Spectrogram — Right | Canvas heatmap | 0 | same endpoint filtered Right | own sub-chart |
| 14 | FFT Spectrogram — Left | Canvas heatmap | 0 | `/spectrogram/fft_left` | 0–20 Hz, 40 bins, `Clinical EEG` colormap |
| 15 | FFT Spectrogram — Right | Canvas heatmap | 0 | `/spectrogram/fft_right` | own sub-chart (see §FFT caveats) |
| 16 | Asymmetry Spectrogram — Hemi | Canvas heatmap | 0 | `/spectrogram/asymmetry_hemi` | RdBu — red = R>L, blue = L>R |
| 17 | aEEG — Left Hemisphere | Band envelope | 0 | `aeeg_left_max` + `aeeg_left_min` | blue fill, log-y. Other percentiles available: `aeeg_left_p50`, `aeeg_left_p75`, `aeeg_left_p25`. |
| 18 | aEEG — Right Hemisphere | Band envelope | 1 | `aeeg_right_max` + `aeeg_right_min` | red fill, overlays L → purple. Same percentile companions as Left. |
| 19 | Suppression — Left | Filled 0–1 line | 0 | `suppression_left` | blue |
| 20 | Suppression — Right | Filled 0–1 line | 1 | `suppression_right` | overlays L |
| 21 | Heart Rate (EKG proxy) | Line | 0 | `heart_rate` | raw EKG not at epoch cadence — HR proxy |

---

## Panel 2 — aEEG

aEEG-focused view with seizure context.

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | Artifact Intensity | line | 0 | `artifact_intensity_*` |
| 2 | P14 Probability | filled area | 0 | `seizure_probability_p14` |
| 3 | P14 Detections | ticks | 1 | `seizure_detection_p14` |
| 4 | Spike Burst Density | **placeholder** | 0 | `EventDensity SpikeBurst` — not produced |
| 5 | Rhythmicity Spectrogram — L | canvas | 0 | `/spectrogram/rhythmicity` (L) |
| 6 | Rhythmicity Spectrogram — R | canvas | 0 | `/spectrogram/rhythmicity` (R) |
| 7 | Asymmetry Spectrogram — Hemi | canvas | 0 | `/spectrogram/asymmetry_hemi` |
| 8 | aEEG — Left | band | 0 | `aeeg_left_*` |
| 9 | aEEG — Right | band | 1 | `aeeg_right_*` → L+R overlay |

> Persyst's full aEEG panel also has 4 EventDensity regional spike rows. Backend doesn't emit them — omitted in the rebuild.

---

## Panel 3 — Asymmetry

REASI indices + asymmetry spectrograms per region.

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | REASI 0–5 Hz — Hemi (delta) | diverging area | 0 | `asymmetry_reasi_delta_hemisphere` |
| 2 | REASI 6–14 Hz — Hemi (alpha) | diverging area | 0 | `asymmetry_reasi_alpha_hemisphere` |
| 3 | Asymmetry Spectrogram — Anterior | canvas RdBu | 0 | `/spectrogram/asymmetry_ant` |
| 4 | Asymmetry Spectrogram — Posterior | canvas RdBu | 0 | `/spectrogram/asymmetry_post` |
| 5 | Asymmetry Spectrogram — Temporal | canvas RdBu | 0 | `/spectrogram/asymmetry_temp` |
| 6 | Asymmetry Spectrogram — Parasagittal | canvas RdBu | 0 | `/spectrogram/asymmetry_parasag` |
| 7 | aEEG — Left | band | 0 | `aeeg_left_*` |
| 8 | aEEG — Right | band | 1 | `aeeg_right_*` |

---

## Panel 4 — Suppression Ratio

Burst-suppression assessment. aEEG L and R are stand-alone here (different from Comprehensive — no overlay per spec).

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | aEEG — Left | band | 0 | `aeeg_left_*` |
| 2 | aEEG — Right | band | 0 | `aeeg_right_*` stand-alone |
| 3 | Suppression — Left | filled 0–1 | 0 | `suppression_left` |
| 4 | Suppression — Right | filled 0–1 | 1 | `suppression_right` overlays L |
| 5 | Rhythmicity Spectrogram — Left | canvas | 0 | `/spectrogram/rhythmicity` (L) |
| 6 | Rhythmicity Spectrogram — Right | canvas | 0 | `/spectrogram/rhythmicity` (R) |

---

## Panel 5 — Power by Frequency Band

Absolute FFT power per epoch (no temporal smoothing). L and R are separate sub-charts per Persyst XML. Sourced from the bare `FFT_Power <band> <Side> Hemisphere_avg` instruments rather than their `Time Avg <0,120>` counterparts: the raw per-epoch columns are present in every panel, the averaged ones only in `Research-TimeAverages`.

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | Artifact Intensity | line | 0 | `artifact_intensity_*` |
| 2 | Delta (1–4 Hz) — Left | line log-y | 0 | `fft_delta_left_hemisphere` |
| 3 | Delta (1–4 Hz) — Right | line log-y | 0 | `fft_delta_right_hemisphere` |
| 4 | Theta (4–8 Hz) — Left | line log-y | 0 | `fft_theta_left_hemisphere` |
| 5 | Theta (4–8 Hz) — Right | line log-y | 0 | `fft_theta_right_hemisphere` |
| 6 | Alpha (8–13 Hz) — Left | line log-y | 0 | `fft_alpha_left_hemisphere` |
| 7 | Alpha (8–13 Hz) — Right | line log-y | 0 | `fft_alpha_right_hemisphere` |
| 8 | Beta (13–20 Hz) — Left | line log-y | 0 | `fft_beta_left_hemisphere` |
| 9 | Asymmetry Spectrogram — Hemi | canvas | 0 | `/spectrogram/asymmetry_hemi` |

> **Beta:** the canonical 13–20 Hz Beta L vs R comes from `Time Avg <0,120> [FFT_Power 13-20 Right Hemisphere_avg]` and its left twin, both present in the `Research-TimeAverages` panel. `fft_beta_wide_{left,right}_hemisphere` (13–30 Hz) is **pipeline-derived** from spectrogram bins, not a Persyst instrument, and is flagged `derived: true` in the data dictionary — do not read it as a native band.
>
> Persyst XML has a 10th row `Time Avg <0,120> []` (empty expression). Skipped.

---

## Panel 6 — Relative Alpha Variability (Quadrant)

RAV (6–14 / 1–20 Hz) × L/R × 3 regions. L and R are separate sub-charts per Persyst XML.

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | RAV — Left Hemisphere | line | 0 | `rav_left_hemisphere` |
| 2 | RAV — Right Hemisphere | line | 0 | `rav_right_hemisphere` |
| 3 | RAV — Left Anterior | line | 0 | `rav_left_anterior` |
| 4 | RAV — Right Anterior | line | 0 | `rav_right_anterior` |
| 5 | RAV — Left Posterior | line | 0 | `rav_left_posterior` |
| 6 | RAV — Right Posterior | line | 0 | `rav_right_posterior` |
| 7 | Asymmetry Spectrogram — Hemi | canvas RdBu | 0 | `/spectrogram/asymmetry_hemi` |
| 8 | EASI 0–20 — Hemi | filled area | 0 | `asymmetry_easi_broadband_hemisphere` |
| 9 | REASI 0–20 — Hemi | filled area | 1 | `asymmetry_reasi_broadband_hemisphere` — overlays EASI |
| 10 | aEEG — Left | band | 0 | `aeeg_left_*` |
| 11 | aEEG — Right | band | 1 | `aeeg_right_*` overlay |

> **Same MMX parser bug as ADR**: `alpha_variability` family goes through the same `extract_hemisphere` / `extract_region` path. Backend schema currently tags I80/I82/I83/I85 etc. as "left"/"right" correctly for RAV, so this family is less affected — but I81/I84 hemisphere entries still need verification.

---

## Panel 7 — Alpha-Delta Ratios (Quadrant)

ADR (8–13 / 1–4 Hz) × L/R × 3 regions. L and R are **overlaid** in this panel (unlike RAV).

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | ADR — Left Hemisphere | line | 0 | `adr_avg_left_hemisphere` |
| 2 | ADR — Right Hemisphere | line | 1 | `adr_avg_right_hemisphere` overlays L |
| 3 | ADR — Left Anterior | line | 0 | `adr_avg_left_anterior` |
| 4 | ADR — Right Anterior | line | 1 | `adr_avg_right_anterior` overlays L |
| 5 | ADR — Left Posterior | line | 0 | `adr_avg_left_posterior` |
| 6 | ADR — Right Posterior | line | 1 | `adr_avg_right_posterior` overlays L |
| 7 | Asymmetry Spectrogram — Hemi | canvas RdBu | 0 | `/spectrogram/asymmetry_hemi` |
| 8 | EASI 0–20 — Hemi | filled area | 0 | `asymmetry_easi_broadband_hemisphere` |
| 9 | REASI 0–20 — Hemi | filled area | 1 | `asymmetry_reasi_broadband_hemisphere` overlays EASI |
| 10 | aEEG — Left | band | 0 | `aeeg_left_*` |
| 11 | aEEG — Right | band | 1 | `aeeg_right_*` overlay |

---

## Panel 8 — SEF and SR

Spectral Edge Frequency percentiles + Burst-Suppression Ratio. Every row stand-alone.

> **Suppression slug semantics (changed 2026-05-27):** `suppression_left` and
> `suppression_right` are the **whole-hemisphere** values (BSR Left/Right
> Hemisphere instruments). Focal regions are explicitly named:
> `suppression_left_anterior`, `suppression_left_posterior`,
> `suppression_right_anterior`, `suppression_right_posterior`. `suppression_all`
> is the whole-brain (All 10-20) variant. Previously the bare `suppression_left`
> /`suppression_right` slugs collided across regions and silently picked Anterior
> as canonical; that has been fixed in `column_mapper.py`. The position-based
> `_v{N}` suffix in `segment_merge.py` replaces the old `_s{sub_index}` / raw
> I-code (`_i{group}_{sub}`) suffixes — slugs no longer embed I-codes.

| # | Sub-chart | Render | Overlap | Source |
|---|---|---|---|---|
| 1 | SEF95 — All 10-20 (whole brain) | line | 0 | `sef_95_all` |
| 2 | SEF95 — Asym Anterior | line | 0 | `sef_95_asym_anterior` |
| 3 | SEF95 — Asym Posterior | line | 0 | `sef_95_asym_posterior` |
| 4 | SEF95 — Left Anterior | line | 0 | `sef_95_left_anterior` |
| 5 | SEF95 — Left Posterior | line | 0 | `sef_95_left_posterior` |
| 6 | SEF95 — Right Anterior | line | 0 | `sef_95_right_anterior` |
| 7 | SEF95 — Right Posterior | line | 0 | `sef_95_right_posterior` |
| 8 | SEF50 — All 10-20 (whole brain) | line | 0 | `sef_50_all` |
| 9 | SEF75 — All 10-20 (whole brain) | line | 0 | `sef_75_all` |
| 10 | SEF90 — All 10-20 (whole brain) | line | 0 | `sef_90_all` |
| 11 | Suppression Ratio — Left | filled 0–1 | 0 | `suppression_left` |
| 12 | Suppression Ratio — Right | filled 0–1 | 0 | `suppression_right` |
| 13 | Suppression Ratio — All 10-20 (whole brain) | filled 0–1 | 0 | `suppression_all` |

---

## FFT Spectrogram caveats — interpreting L vs R

- The raw FFT spectrogram shows **absolute power per frequency bin**. If left and right hemispheres have similar background power, the L and R panels will **look visually identical** even though the data differs.
- The current renderer picks a colour range per-spectrogram, so small absolute differences can produce deceptive visuals.
- The **asymmetry spectrogram** shows `(L−R)/(L+R)` per bin — it amplifies small differences and can show clear red (R>L) or blue (L>R) even when raw L and R look similar.
- For direct L vs R comparison, prefer the asymmetry spectrogram over eyeballing two hot-colour FFT panels.

---

## Workbench KPI Sources

| KPI | Source field | Notes |
|---|---|---|
| Total Duration | `qc.recording_duration_hours` | QC display value; audit against timestamp-derived duration before publication. |
| Usable Data | `qc.usable_hours` | Artifact-clean duration estimate. |
| Artifact | `qc.artifact_pct` | Percent rejected by configured artifact mode. |
| Seizure Events | `seizure.seizure_events` | Algorithmic Persyst-trend event count, not adjudicated seizure count. |
| Suppression | `qc.median_suppression_pct` | Median suppression ratio across usable epochs. |
| Usable Epochs | `qc.usable_epochs` / `qc.total_epochs` | Row counts after artifact filtering. |

---

## How to extend this

- Authoritative panel order: `frontend/src/panels/manifest.ts`
- Instrument row factories (colour, height, description, traces): `frontend/src/panels/instruments.ts`
- Persyst name → backend column resolver: `frontend/src/panels/columnResolver.ts`
- Spectrogram freq ranges: `qeeg/constants.py::SPECTROGRAM_FREQ_MAP`
- Backend column naming: `qeeg/ingestion/column_mapper.py::generate_common_name`
- Obsidian reference notes: `E:\Craig_Vault\Projects\qEEG Analysis Pipeline\Persyst Reference\`
