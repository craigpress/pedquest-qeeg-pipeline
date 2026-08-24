# Column map — Research Trends

**301 columns** across 25 families, generated from the shipped template through the production resolution path, so it cannot drift from what ingestion does.

Full record (all 34 fields per column): [`COLUMN_MAP_V10_RESEARCH_TRENDS.csv`](COLUMN_MAP_V10_RESEARCH_TRENDS.csv) · [`.json`](COLUMN_MAP_V10_RESEARCH_TRENDS.json). The `.html` alongside them is a richer browser view, but GitHub will not render it — clone the repo and open it locally.

## Evidence tiers

Every column carries one. Read it before relying on the column.

| Tier | Meaning | Count |
|---|---|---:|
| `P-DOC` | vendor-documented | 143 |
| `P-COMM` | direct Persyst communication | 87 |
| `MMX` | read from the template | 64 |
| `EMP` | empirical / inferred — provisional | 7 |

## Families

| Family | Columns | Units |
|---|---:|---|
| [`adr`](#adr) | 18 | ratio of µV amplitudes (dimensionless); clamped at Ratio … |
| [`aeeg`](#aeeg) | 25 | µV (peak-to-peak) |
| [`alpha_variability`](#alpha-variability) | 15 | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless);… |
| [`annotation`](#annotation) | 1 | text |
| [`artifact_detector`](#artifact-detector) | 18 |  **— discarded at ingestion, never exported** |
| [`artifact_intensity`](#artifact-intensity) | 3 | muscle: µV (per Persyst 2026-08-20; help text says µV² — … |
| [`asymmetry`](#asymmetry) | 11 | % (EASI 0–100 magnitude; REASI −100 to +100, + = right>left) *(bins summarised below)* |
| [`coherence_spectrogram`](#coherence-spectrogram) | 5 | coherence (0–1) *(bins summarised below)* |
| [`electrode_quality`](#electrode-quality) | 22 | dimensionless, 0=clean → 1.0; >1.0 = above impedance disc… |
| [`fft_power`](#fft-power) | 54 | µV (amplitude; MMX PowerType=1 — NOT µV² power) |
| [`other`](#other) | 1 |  |
| [`peak_envelope`](#peak-envelope) | 9 | µV |
| [`rda`](#rda) | 3 | rhythmicity index |
| [`relative_power`](#relative-power) | 36 | band/broadband ratio of µV amplitudes (dimensionless); cl… |
| [`rhythmic_delta`](#rhythmic-delta) | 6 | boolean (0/1) |
| [`rhythmicity`](#rhythmicity) | 16 | rhythmicity index *(bins summarised below)* |
| [`seizure_burden`](#seizure-burden) | 2 | % (0–100) or category code per variant |
| [`seizure_detection`](#seizure-detection) | 3 | boolean (0/1) |
| [`seizure_notification`](#seizure-notification) | 1 | boolean (0/1) |
| [`seizure_probability`](#seizure-probability) | 1 | probability (0–1) |
| [`sleep`](#sleep) | 8 | sleep stage code |
| [`spectral_edge`](#spectral-edge) | 12 | Hz |
| [`spike_density`](#spike-density) | 16 | spikes/sec |
| [`status_epilepticus`](#status-epilepticus) | 6 | binary (0/1) or % (0–100) per variant. PERCENT variants f… |
| [`suppression_ratio`](#suppression-ratio) | 9 | % (0–100) |

### adr

**Units:** ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NOT a power ratio — equals the square root of a conventional power-based ADR, so do not compare directly to published values.

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `adr_all` | `I103_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, All 10-20 | FFT_PowerRatio 8-13//1-4 All 10-20_avg | P-DOC |
| `adr_anterior` | `I110_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Anterior | FFT_PowerRatio 8-13//1-4 Anterior_avg | P-DOC |
| `adr_left_anterior` | `I104_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Anterior | FFT_PowerRatio 8-13//1-4 Left Anterior_avg | P-DOC |
| `adr_left_hemisphere` | `I105_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Hemisphere | FFT_PowerRatio 8-13//1-4 Left Hemisphere_avg | P-DOC |
| `adr_left_posterior` | `I106_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Posterior | FFT_PowerRatio 8-13//1-4 Left Posterior_avg | P-DOC |
| `adr_posterior` | `I111_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Posterior | FFT_PowerRatio 8-13//1-4 Posterior_avg | P-DOC |
| `adr_right_anterior` | `I107_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Anterior | FFT_PowerRatio 8-13//1-4 Right Anterior_avg | P-DOC |
| `adr_right_hemisphere` | `I108_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Hemisphere | FFT_PowerRatio 8-13//1-4 Right Hemisphere_avg | P-DOC |
| `adr_right_posterior` | `I109_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Posterior | FFT_PowerRatio 8-13//1-4 Right Posterior_avg | P-DOC |
| `tdr_all` | `I85_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, All 10-20 | FFT_PowerRatio 4-8//1-4 All 10-20_avg | P-DOC |
| `tdr_anterior` | `I92_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Anterior | FFT_PowerRatio 4-8//1-4 Anterior_avg | P-DOC |
| `tdr_left_anterior` | `I86_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Anterior | FFT_PowerRatio 4-8//1-4 Left Anterior_avg | P-DOC |
| `tdr_left_hemisphere` | `I87_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Hemisphere | FFT_PowerRatio 4-8//1-4 Left Hemisphere_avg | P-DOC |
| `tdr_left_posterior` | `I88_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Posterior | FFT_PowerRatio 4-8//1-4 Left Posterior_avg | P-DOC |
| `tdr_posterior` | `I93_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Posterior | FFT_PowerRatio 4-8//1-4 Posterior_avg | P-DOC |
| `tdr_right_anterior` | `I89_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Anterior | FFT_PowerRatio 4-8//1-4 Right Anterior_avg | P-DOC |
| `tdr_right_hemisphere` | `I90_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Hemisphere | FFT_PowerRatio 4-8//1-4 Right Hemisphere_avg | P-DOC |
| `tdr_right_posterior` | `I91_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Posterior | FFT_PowerRatio 4-8//1-4 Right Posterior_avg | P-DOC |

### aeeg

**Units:** µV (peak-to-peak)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `aeeg_anterior_max` | `I4_1` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_min` | `I4_2` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p25` | `I4_5` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p50` | `I4_3` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p75` | `I4_4` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_left_max` | `I2_1` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_min` | `I2_2` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p25` | `I2_5` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p50` | `I2_3` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p75` | `I2_4` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_max` | `I1_1` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_min` | `I1_2` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p25` | `I1_5` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p50` | `I1_3` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p75` | `I1_4` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_posterior_max` | `I5_1` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_min` | `I5_2` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p25` | `I5_5` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p50` | `I5_3` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p75` | `I5_4` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_right_max` | `I3_1` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_min` | `I3_2` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p25` | `I3_5` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p50` | `I3_3` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p75` | `I3_4` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |

### alpha_variability

**Units:** RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rav_all` | `I94_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, All 10-20 | FFT_PowerRatio 6-14//1-20 All 10-20_avg | MMX |
| `rav_anterior` | `I101_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Anterior | FFT_PowerRatio 6-14//1-20 Anterior_avg | MMX |
| `rav_avg_left_anterior` | `I121_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Anterior,… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Anterior_avg] | MMX |
| `rav_avg_left_hemisphere` | `I122_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Hemispher… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Hemisphere_avg] | MMX |
| `rav_avg_left_posterior` | `I123_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Posterior… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Posterior_avg] | MMX |
| `rav_avg_right_anterior` | `I124_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Anterior… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Anterior_avg] | MMX |
| `rav_avg_right_hemisphere` | `I125_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Hemisphe… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Hemisphere_avg] | MMX |
| `rav_avg_right_posterior` | `I126_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Posterio… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Posterior_avg] | MMX |
| `rav_left_anterior` | `I95_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Anterior | FFT_PowerRatio 6-14//1-20 Left Anterior_avg | MMX |
| `rav_left_hemisphere` | `I96_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Hemisphere | FFT_PowerRatio 6-14//1-20 Left Hemisphere_avg | MMX |
| `rav_left_posterior` | `I97_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Posterior | FFT_PowerRatio 6-14//1-20 Left Posterior_avg | MMX |
| `rav_posterior` | `I102_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Posterior | FFT_PowerRatio 6-14//1-20 Posterior_avg | MMX |
| `rav_right_anterior` | `I98_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Anterior | FFT_PowerRatio 6-14//1-20 Right Anterior_avg | MMX |
| `rav_right_hemisphere` | `I99_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Hemisphere | FFT_PowerRatio 6-14//1-20 Right Hemisphere_avg | MMX |
| `rav_right_posterior` | `I100_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Posterior | FFT_PowerRatio 6-14//1-20 Right Posterior_avg | MMX |

### annotation

**Units:** text

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `annotation` | `I239_1` | text | Comment |  | P-DOC |

### artifact_detector

> **These 18 columns are present in the export and deliberately dropped at ingestion.** They never reach the dataframe, the schema, or any output.
>
> Mike 2026-08-20: 18 internal classifiers; discard
>
> Their `variable_name` values here are positional placeholders, not identities read from the export — which is part of why the family is discarded. See `docs/ARTIFACT_EXCLUSION.md`.


### artifact_intensity

**Units:** muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirmed). V-Eye / L-Eye: probability 0.0–1.0

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `artifact_intensity_emg` | `I7_1` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |
| `artifact_intensity_eye_horizontal` | `I7_3` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |
| `artifact_intensity_eye_vertical` | `I7_2` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |

### asymmetry

**Units:** % (EASI 0–100 magnitude; REASI −100 to +100, + = right>left)

11 columns — one per frequency bin, across 11 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `asymmetry_easi_broadband_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_parasagittal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_posterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_temporal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_broadband_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_parasagittal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_posterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_temporal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_hemisphere` | 1 | — | `P-DOC` |

### coherence_spectrogram

**Units:** coherence (0–1)

5 columns — one per frequency bin, across 5 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `coherence_avg_c3p3` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_f3c3` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_p3o1` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_p7o1` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_t7p7` | 1 | 0.32–0.32 Hz | `MMX` |

### electrode_quality

**Units:** dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect threshold. Clamped at the MMX display Maximum (1.2 in this template)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `esq_ch01` | `I30_1` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch02` | `I30_2` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch03` | `I30_3` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch04` | `I30_4` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch05` | `I30_5` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch06` | `I30_6` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch07` | `I30_7` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch08` | `I30_8` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch09` | `I30_9` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch10` | `I30_10` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch11` | `I30_11` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch12` | `I30_12` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch13` | `I30_13` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch14` | `I30_14` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch15` | `I30_15` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch16` | `I30_16` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch17` | `I30_17` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch18` | `I30_18` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch19` | `I30_19` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch20` | `I30_20` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch21` | `I30_21` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch22` | `I30_22` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |

### fft_power

**Units:** µV (amplitude; MMX PowerType=1 — NOT µV² power)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `fft_alpha_all` | `I76_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, All 10-20 | FFT_Power 8-13 All 10-20_avg | P-DOC |
| `fft_alpha_anterior` | `I83_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Anterior | FFT_Power 8-13 Anterior_avg | P-DOC |
| `fft_alpha_left_anterior` | `I77_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Anterior | FFT_Power 8-13 Left Anterior_avg | P-DOC |
| `fft_alpha_left_hemisphere` | `I78_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Hemisphere | FFT_Power 8-13 Left Hemisphere_avg | P-DOC |
| `fft_alpha_left_posterior` | `I79_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Posterior | FFT_Power 8-13 Left Posterior_avg | P-DOC |
| `fft_alpha_posterior` | `I84_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Posterior | FFT_Power 8-13 Posterior_avg | P-DOC |
| `fft_alpha_right_anterior` | `I80_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Anterior | FFT_Power 8-13 Right Anterior_avg | P-DOC |
| `fft_alpha_right_hemisphere` | `I81_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Hemisphere | FFT_Power 8-13 Right Hemisphere_avg | P-DOC |
| `fft_alpha_right_posterior` | `I82_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Posterior | FFT_Power 8-13 Right Posterior_avg | P-DOC |
| `fft_beta_all` | `I49_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, All 10-20 | FFT_Power 13-20 All 10-20_avg | P-DOC |
| `fft_beta_anterior` | `I57_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Anterior | FFT_Power 13-20 Anterior_avg | P-DOC |
| `fft_beta_left_anterior` | `I50_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Anterior | FFT_Power 13-20 Left Anterior_avg | P-DOC |
| `fft_beta_left_hemisphere` | `I51_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Hemisphere | FFT_Power 13-20 Left Hemisphere_avg | P-DOC |
| `fft_beta_left_posterior` | `I52_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Posterior | FFT_Power 13-20 Left Posterior_avg | P-DOC |
| `fft_beta_posterior` | `I58_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Posterior | FFT_Power 13-20 Posterior_avg | P-DOC |
| `fft_beta_right_anterior` | `I53_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Anterior | FFT_Power 13-20 Right Anterior_avg | P-DOC |
| `fft_beta_right_hemisphere` | `I54_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Hemisphere | FFT_Power 13-20 Right Hemisphere_avg | P-DOC |
| `fft_beta_right_posterior` | `I55_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Posterior | FFT_Power 13-20 Right Posterior_avg | P-DOC |
| `fft_beta_wide_all` | `I56_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, All 10-20 | FFT_Power 13-30 All 10-20_avg | P-DOC |
| `fft_beta_wide_anterior` | `I59_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Anterior | FFT_Power 13-30 Anterior_avg | P-DOC |
| `fft_beta_wide_left_anterior` | `I60_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Anterior | FFT_Power 13-30 Left Anterior_avg | P-DOC |
| `fft_beta_wide_left_hemisphere` | `I65_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Hemisphere | FFT_Power 13-30 Left Hemisphere_avg | P-DOC |
| `fft_beta_wide_left_posterior` | `I61_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Posterior | FFT_Power 13-30 Left Posterior_avg | P-DOC |
| `fft_beta_wide_posterior` | `I62_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Posterior | FFT_Power 13-30 Posterior_avg | P-DOC |
| `fft_beta_wide_right_anterior` | `I63_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Anterior | FFT_Power 13-30 Right Anterior_avg | P-DOC |
| `fft_beta_wide_right_hemisphere` | `I66_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Hemisphere | FFT_Power 13-30 Right Hemisphere_avg | P-DOC |
| `fft_beta_wide_right_posterior` | `I64_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Posterior | FFT_Power 13-30 Right Posterior_avg | P-DOC |
| `fft_delta_all` | `I40_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, All 10-20 | FFT_Power 1-4 All 10-20_avg | P-DOC |
| `fft_delta_anterior` | `I47_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Anterior | FFT_Power 1-4 Anterior_avg | P-DOC |
| `fft_delta_left_anterior` | `I41_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Anterior | FFT_Power 1-4 Left Anterior_avg | P-DOC |
| `fft_delta_left_hemisphere` | `I42_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Hemisphere | FFT_Power 1-4 Left Hemisphere_avg | P-DOC |
| `fft_delta_left_posterior` | `I43_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Posterior | FFT_Power 1-4 Left Posterior_avg | P-DOC |
| `fft_delta_posterior` | `I48_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Posterior | FFT_Power 1-4 Posterior_avg | P-DOC |
| `fft_delta_right_anterior` | `I44_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Anterior | FFT_Power 1-4 Right Anterior_avg | P-DOC |
| `fft_delta_right_hemisphere` | `I45_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Hemisphere | FFT_Power 1-4 Right Hemisphere_avg | P-DOC |
| `fft_delta_right_posterior` | `I46_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Posterior | FFT_Power 1-4 Right Posterior_avg | P-DOC |
| `fft_power_all` | `I31_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, All 10-20 | FFT_Power 1-20 All 10-20_avg | P-DOC |
| `fft_power_anterior` | `I38_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Anterior | FFT_Power 1-20 Anterior_avg | P-DOC |
| `fft_power_left_anterior` | `I32_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Anterior | FFT_Power 1-20 Left Anterior_avg | P-DOC |
| `fft_power_left_hemisphere` | `I33_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Hemisphere | FFT_Power 1-20 Left Hemisphere_avg | P-DOC |
| `fft_power_left_posterior` | `I34_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Posterior | FFT_Power 1-20 Left Posterior_avg | P-DOC |
| `fft_power_posterior` | `I39_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Posterior | FFT_Power 1-20 Posterior_avg | P-DOC |
| `fft_power_right_anterior` | `I35_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Anterior | FFT_Power 1-20 Right Anterior_avg | P-DOC |
| `fft_power_right_hemisphere` | `I36_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Hemisphere | FFT_Power 1-20 Right Hemisphere_avg | P-DOC |
| `fft_power_right_posterior` | `I37_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Posterior | FFT_Power 1-20 Right Posterior_avg | P-DOC |
| `fft_theta_all` | `I67_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, All 10-20 | FFT_Power 4-8 All 10-20_avg | P-DOC |
| `fft_theta_anterior` | `I74_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Anterior | FFT_Power 4-8 Anterior_avg | P-DOC |
| `fft_theta_left_anterior` | `I68_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Anterior | FFT_Power 4-8 Left Anterior_avg | P-DOC |
| `fft_theta_left_hemisphere` | `I69_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Hemisphere | FFT_Power 4-8 Left Hemisphere_avg | P-DOC |
| `fft_theta_left_posterior` | `I70_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Posterior | FFT_Power 4-8 Left Posterior_avg | P-DOC |
| `fft_theta_posterior` | `I75_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Posterior | FFT_Power 4-8 Posterior_avg | P-DOC |
| `fft_theta_right_anterior` | `I71_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Anterior | FFT_Power 4-8 Right Anterior_avg | P-DOC |
| `fft_theta_right_hemisphere` | `I72_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Hemisphere | FFT_Power 4-8 Right Hemisphere_avg | P-DOC |
| `fft_theta_right_posterior` | `I73_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Posterior | FFT_Power 4-8 Right Posterior_avg | P-DOC |

### other

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `other_i240s1` | `I240_1` |  | Time |  | EMP |

### peak_envelope

**Units:** µV

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `peak_envelope` | `I112_1` | µV | PeakEnvelope, 2 - 20 Hz, All 10-20 | PeakEnvelope 2-20 All 10-20_avg | P-DOC |
| `peak_envelope_anterior` | `I119_1` | µV | PeakEnvelope, 2 - 20 Hz, Anterior | PeakEnvelope 2-20 Anterior_avg | P-DOC |
| `peak_envelope_left_anterior` | `I113_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Anterior | PeakEnvelope 2-20 Left Anterior_avg | P-DOC |
| `peak_envelope_left_hemisphere` | `I114_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Hemisphere | PeakEnvelope 2-20 Left Hemisphere_avg | P-DOC |
| `peak_envelope_left_posterior` | `I115_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Posterior | PeakEnvelope 2-20 Left Posterior_avg | P-DOC |
| `peak_envelope_posterior` | `I120_1` | µV | PeakEnvelope, 2 - 20 Hz, Posterior | PeakEnvelope 2-20 Posterior_avg | P-DOC |
| `peak_envelope_right_anterior` | `I116_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Anterior | PeakEnvelope 2-20 Right Anterior_avg | P-DOC |
| `peak_envelope_right_hemisphere` | `I117_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Hemisphere | PeakEnvelope 2-20 Right Hemisphere_avg | P-DOC |
| `peak_envelope_right_posterior` | `I118_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Posterior | PeakEnvelope 2-20 Right Posterior_avg | P-DOC |

### rda

**Units:** rhythmicity index

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rda_bilateral` | `I127_1` | rhythmicity index | Rhythmic delta indicator (blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left… | P-COMM |
| `rda_left` | `I128_1` | rhythmicity index | Rhythmic delta indicator (blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left… | P-COMM |
| `rda_right` | `I129_1` | rhythmicity index | Rhythmic delta indicator (blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Righ… | P-COMM |

### relative_power

**Units:** band/broadband ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NOT conventional relative power (band power ÷ total power) — equals its square root.

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rel_alpha_all` | `I195_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, All 10-20 | FFT_PowerRatio 8-13//1-30 All 10-20_avg | MMX |
| `rel_alpha_anterior` | `I196_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Anterior | FFT_PowerRatio 8-13//1-30 Anterior_avg | MMX |
| `rel_alpha_left_anterior` | `I197_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Anterior | FFT_PowerRatio 8-13//1-30 Left Anterior_avg | MMX |
| `rel_alpha_left_hemisphere` | `I198_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Hemisphere | FFT_PowerRatio 8-13//1-30 Left Hemisphere_avg | MMX |
| `rel_alpha_left_posterior` | `I199_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Posterior | FFT_PowerRatio 8-13//1-30 Left Posterior_avg | MMX |
| `rel_alpha_posterior` | `I200_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Posterior | FFT_PowerRatio 8-13//1-30 Posterior_avg | MMX |
| `rel_alpha_right_anterior` | `I201_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Anterior | FFT_PowerRatio 8-13//1-30 Right Anterior_avg | MMX |
| `rel_alpha_right_hemisphere` | `I202_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Hemisphere | FFT_PowerRatio 8-13//1-30 Right Hemisphere_avg | MMX |
| `rel_alpha_right_posterior` | `I203_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Posterior | FFT_PowerRatio 8-13//1-30 Right Posterior_avg | MMX |
| `rel_beta_wide_all` | `I204_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, All 10-20 | FFT_PowerRatio 13-30//1-30 All 10-20_avg | MMX |
| `rel_beta_wide_anterior` | `I205_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Anterior | FFT_PowerRatio 13-30//1-30 Anterior_avg | MMX |
| `rel_beta_wide_left_anterior` | `I206_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Anterior | FFT_PowerRatio 13-30//1-30 Left Anterior_avg | MMX |
| `rel_beta_wide_left_hemisphere` | `I207_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Hemisphere | FFT_PowerRatio 13-30//1-30 Left Hemisphere_avg | MMX |
| `rel_beta_wide_left_posterior` | `I208_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Posterior | FFT_PowerRatio 13-30//1-30 Left Posterior_avg | MMX |
| `rel_beta_wide_posterior` | `I209_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Posterior | FFT_PowerRatio 13-30//1-30 Posterior_avg | MMX |
| `rel_beta_wide_right_anterior` | `I210_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Anterior | FFT_PowerRatio 13-30//1-30 Right Anterior_avg | MMX |
| `rel_beta_wide_right_hemisphere` | `I211_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Hemisphere | FFT_PowerRatio 13-30//1-30 Right Hemisphere_avg | MMX |
| `rel_beta_wide_right_posterior` | `I212_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Posterior | FFT_PowerRatio 13-30//1-30 Right Posterior_avg | MMX |
| `rel_delta_all` | `I213_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, All 10-20 | FFT_PowerRatio 1-4//1-30 All 10-20_avg | MMX |
| `rel_delta_anterior` | `I214_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Anterior | FFT_PowerRatio 1-4//1-30 Anterior_avg | MMX |
| `rel_delta_left_anterior` | `I215_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Anterior | FFT_PowerRatio 1-4//1-30 Left Anterior_avg | MMX |
| `rel_delta_left_hemisphere` | `I216_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Hemisphere | FFT_PowerRatio 1-4//1-30 Left Hemisphere_avg | MMX |
| `rel_delta_left_posterior` | `I217_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Posterior | FFT_PowerRatio 1-4//1-30 Left Posterior_avg | MMX |
| `rel_delta_posterior` | `I218_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Posterior | FFT_PowerRatio 1-4//1-30 Posterior_avg | MMX |
| `rel_delta_right_anterior` | `I219_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Anterior | FFT_PowerRatio 1-4//1-30 Right Anterior_avg | MMX |
| `rel_delta_right_hemisphere` | `I220_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Hemisphere | FFT_PowerRatio 1-4//1-30 Right Hemisphere_avg | MMX |
| `rel_delta_right_posterior` | `I221_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Posterior | FFT_PowerRatio 1-4//1-30 Right Posterior_avg | MMX |
| `rel_theta_all` | `I222_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, All 10-20 | FFT_PowerRatio 4-8//1-30 All 10-20_avg | MMX |
| `rel_theta_anterior` | `I223_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Anterior | FFT_PowerRatio 4-8//1-30 Anterior_avg | MMX |
| `rel_theta_left_anterior` | `I224_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Anterior | FFT_PowerRatio 4-8//1-30 Left Anterior_avg | MMX |
| `rel_theta_left_hemisphere` | `I225_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Hemisphere | FFT_PowerRatio 4-8//1-30 Left Hemisphere_avg | MMX |
| `rel_theta_left_posterior` | `I226_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Posterior | FFT_PowerRatio 4-8//1-30 Left Posterior_avg | MMX |
| `rel_theta_posterior` | `I227_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Posterior | FFT_PowerRatio 4-8//1-30 Posterior_avg | MMX |
| `rel_theta_right_anterior` | `I228_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Anterior | FFT_PowerRatio 4-8//1-30 Right Anterior_avg | MMX |
| `rel_theta_right_hemisphere` | `I229_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Hemisphere | FFT_PowerRatio 4-8//1-30 Right Hemisphere_avg | MMX |
| `rel_theta_right_posterior` | `I230_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Posterior | FFT_PowerRatio 4-8//1-30 Right Posterior_avg | MMX |

### rhythmic_delta

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rhythmic_delta_left_anterior` | `I19_1` | boolean (0/1) | Boolean LAD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left A… | EMP |
| `rhythmic_delta_left_hemisphere` | `I21_1` | boolean (0/1) | Boolean LRD+ | [[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left … | EMP |
| `rhythmic_delta_left_posterior` | `I20_1` | boolean (0/1) | Boolean LPD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left P… | EMP |
| `rhythmic_delta_right_anterior` | `I22_1` | boolean (0/1) | Boolean RAD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right … | EMP |
| `rhythmic_delta_right_hemisphere` | `I24_1` | boolean (0/1) | Boolean RRD+ | [[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right… | EMP |
| `rhythmic_delta_right_posterior` | `I23_1` | boolean (0/1) | Boolean RPD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right … | EMP |

### rhythmicity

**Units:** rhythmicity index

16 columns — one per frequency bin, across 16 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `rhythmicity_sum_left_anterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_anterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_posterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_posterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_anterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_anterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_posterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_posterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_thresh_left_anterior_lad_gte` | 1 | 1.1–1.1 Hz | `P-COMM` |
| `rhythmicity_thresh_left_anterior_lad_gte_5uv_hz` | 1 | — | `P-COMM` |
| `rhythmicity_thresh_left_posterior_lpd_gte` | 1 | 1.1–1.1 Hz | `P-COMM` |
| `rhythmicity_thresh_left_posterior_lpd_gte_5uv_hz` | 1 | — | `P-COMM` |
| `rhythmicity_thresh_right_anterior_rad_gte` | 1 | 1.1–1.1 Hz | `P-COMM` |
| `rhythmicity_thresh_right_anterior_rad_gte_5uv_hz` | 1 | — | `P-COMM` |
| `rhythmicity_thresh_right_posterior_rpd_gte` | 1 | 1.1–1.1 Hz | `P-COMM` |
| `rhythmicity_thresh_right_posterior_rpd_gte_5uv_hz` | 1 | — | `P-COMM` |

### seizure_burden

**Units:** % (0–100) or category code per variant

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_burden_persyst_category` | `I232_1` | % (0–100) or category code per variant | Seizure Burden - 5 min- Category | Seizure Burden01 | MMX |
| `seizure_burden_persyst_percentage` | `I231_1` | % (0–100) or category code per variant | Seizure Burden - 5 min - Percentage | Seizure Burden | MMX |

### seizure_detection

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_detection_event` | `I142_1` | boolean (0/1) | Seizure Detections (red) and Notifications (gray) | SeizureEventsP14 | P-DOC |
| `seizure_detection_p14` | `I144_1` | boolean (0/1) | Seizure detections | SeizureProbabilityP14 Detections | P-DOC |
| `seizure_notification_event` | `I142_2` | boolean (0/1) | Seizure Detections (red) and Notifications (gray) | SeizureEventsP14 | P-DOC |

### seizure_notification

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_notification_p14` | `I143_1` | boolean (0/1) | Seizure Notifications (P14) | SeizureProbabilityP14 Notifications | P-DOC |

### seizure_probability

**Units:** probability (0–1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_probability_p14_probability` | `I145_1` | probability (0–1) | Seizure probability | SeizureProbabilityP14 Probability | P-DOC |

### sleep

**Units:** sleep stage code

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `sleep_stage_0` | `I148_1` | sleep stage code | Sleep-Wake Stage Indeterminate (yellow=wake; green-blue=N1; light b… | = 0 <0> [SleepStages] | P-DOC |
| `sleep_stage_1` | `I147_1` | sleep stage code | Sleep-Wake Stage N3 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 1 <0> [SleepStages] | P-DOC |
| `sleep_stage_2` | `I152_1` | sleep stage code | Sleep-Wake Stage N2 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 2 <0> [SleepStages] | P-DOC |
| `sleep_stage_3` | `I149_1` | sleep stage code | Sleep-Wake Stage N1 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 3 <0> [SleepStages] | P-DOC |
| `sleep_stage_4` | `I151_1` | sleep stage code | Sleep-Wake Stage REM (yellow=wake; green-blue=N1; light blue=N2; da… | = 4 <0> [SleepStages] | P-DOC |
| `sleep_stage_5` | `I150_1` | sleep stage code | Sleep-Wake Stage Wake (yellow=wake; green-blue=N1; light blue=N2; d… | = 5 <0> [SleepStages] | P-DOC |
| `sleep_stage_display` | `I146_1` | sleep stage code | SleepStages | SleepStages | P-DOC |
| `sleep_wake_state` | `I153_1` | sleep stage code | Sleep-Wake State (yellow=wake; blue=sleep; black=indeterminate), [S… | ColorScaledBars | P-DOC |

### spectral_edge

**Units:** Hz

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `sef_50_all` | `I139_1` | Hz | SEF50, All 10-20 | FFT_Edge 50 0-32 All 10-20_avg | P-DOC |
| `sef_75_all` | `I140_1` | Hz | SEF75, All 10-20 | FFT_Edge 75 0-32 All 10-20_avg | P-DOC |
| `sef_90_all` | `I141_1` | Hz | SEF90, All 10-20 | FFT_Edge 90 0-32 All 10-20_avg | P-DOC |
| `sef_95_all` | `I130_1` | Hz | SEF95, All 10-20 | FFT_Edge 95 0-32 All 10-20_avg | P-DOC |
| `sef_95_anterior` | `I137_1` | Hz | SEF95, Anterior | FFT_Edge 95 0-32 Anterior_avg | P-DOC |
| `sef_95_left_anterior` | `I132_1` | Hz | SEF 95 Left Ant, Left Anterior | FFT_Edge 95 0-32 Left Anterior_avg | P-DOC |
| `sef_95_left_hemisphere` | `I131_1` | Hz | SEF95, Left Hemisphere | FFT_Edge 95 0-32 Left Hemisphere_avg | P-DOC |
| `sef_95_left_posterior` | `I133_1` | Hz | SEF 95 Left Post, Left Posterior | FFT_Edge 95 0-32 Left Posterior_avg | P-DOC |
| `sef_95_posterior` | `I138_1` | Hz | SEF95, Posterior | FFT_Edge 95 0-32 Posterior_avg | P-DOC |
| `sef_95_right_anterior` | `I135_1` | Hz | SEF 95 Right Ant, Right Anterior | FFT_Edge 95 0-32 Right Anterior_avg | P-DOC |
| `sef_95_right_hemisphere` | `I134_1` | Hz | SEF95, Right Hemisphere | FFT_Edge 95 0-32 Right Hemisphere_avg | P-DOC |
| `sef_95_right_posterior` | `I136_1` | Hz | SEF 95 Right Post, Right Posterior | FFT_Edge 95 0-32 Right Posterior_avg | P-DOC |

### spike_density

**Units:** spikes/sec

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `spike_all_foci_per_sec` | `I162_1` | spikes/sec | Spike Detections, all foci (count per sec) | SpikeDensityV1 | P-DOC |
| `spike_bilateral_indicator_per_10s` | `I166_1` | spikes/sec | Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R) | [>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike… | P-DOC |
| `spike_burst` | `I154_1` | spikes/sec | Spike Burst Detections | EventDensity SpikeBurst <Detector,Count_overlap> | P-DOC |
| `spike_generalized_indicator_per_10s` | `I169_1` | spikes/sec | Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R), gree… | [>= 3 <0> [EventDensity SpikeGen <Detector,Count_epoch>01]] AND [>=… | P-DOC |
| `spike_generalized_per_10s` | `I155_1` | spikes/sec | Spike Detections generalized (count per 10s) | EventDensity SpikeGen <Detector,Count_epoch> | P-DOC |
| `spike_generalized_per_sec` | `I156_1` | spikes/sec | Spike Detections generalized (count per sec) | EventDensity SpikeGen <Detector,Count_epoch>01 | P-DOC |
| `spike_generalized_threshold_per_sec` | `I164_1` | spikes/sec | Spike RateThreshold, generalized >=3 per 10 sec, Spike Detections g… | >= 3 <0> [EventDensity SpikeGen <Detector,Count_epoch>01] | P-DOC |
| `spike_left_indicator_per_10s` | `I168_1` | spikes/sec | Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R), gree… | [>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike… | P-DOC |
| `spike_left_per_10s` | `I157_1` | spikes/sec | Spike Detections left hemisphere (count per 10 sec) | EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike C3 OR Spik… | P-DOC |
| `spike_left_per_sec` | `I158_1` | spikes/sec | Spike Detections left hemisphere (count per sec) | EventDensity Spike Fp1 OR Spike FP1 OR Spike F3 OR Spike C3 OR Spik… | P-DOC |
| `spike_left_threshold_per_10s` | `I165_1` | spikes/sec | Spike RateThreshold, left hemisphere >=3 per 10 sec, Spike Detectio… | >= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike … | P-DOC |
| `spike_right_indicator_per_10s` | `I167_1` | spikes/sec | Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R) | [>= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike… | P-DOC |
| `spike_right_per_10s` | `I159_1` | spikes/sec | Spike Detections right hemisphere (count per 10 sec) | EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike C4 OR Spik… | P-DOC |
| `spike_right_per_sec` | `I160_1` | spikes/sec | Spike Detections right hemisphere (count per sec) | EventDensity Spike Fp2 OR Spike FP2 OR Spike F4 OR Spike C4 OR Spik… | P-DOC |
| `spike_right_threshold_per_10s` | `I163_1` | spikes/sec | Spike Rate Threshold, right hemisphere >=3 per 10 sec, Spike Detect… | >= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike … | P-DOC |
| `spike_vertex_per_sec` | `I161_1` | spikes/sec | Spike Detections vertex (count per sec) | EventDensity Spike Fz OR Spike FZ OR Spike Cz OR Spike CZ OR Spike … | P-DOC |

### status_epilepticus

**Units:** binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.050331, never 0; advanced and combined are identical — see docs/DATA_DICTIONARY_v4.md

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `status_epilepticus_persyst_acns_binary` | `I233_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus ACNS Metric (Binary) | Electrographic Status Epilepticus | MMX |
| `status_epilepticus_persyst_acns_percent` | `I234_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus ACNS Metric (Percent) | Electrographic Status Epilepticus01 | MMX |
| `status_epilepticus_persyst_advanced_binary` | `I235_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Advanced Metric (Binary) | Electrographic Status Epilepticus02 | MMX |
| `status_epilepticus_persyst_advanced_percent` | `I236_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Advanced Metric (Percent) | Electrographic Status Epilepticus03 | MMX |
| `status_epilepticus_persyst_combined_binary` | `I237_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Combined Metric (Binary) | Electrographic Status Epilepticus04 | MMX |
| `status_epilepticus_persyst_combined_percent` | `I238_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Combined Metric (Percent) | Electrographic Status Epilepticus05 | MMX |

### suppression_ratio

**Units:** % (0–100)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `suppression_all` | `I178_1` | % (0–100) | Suppression Ratio, All 10-20 | BSR All 10-20_avg | P-DOC |
| `suppression_anterior` | `I185_1` | % (0–100) | Suppression Ratio, Anterior | BSR Anterior_avg | P-DOC |
| `suppression_left` | `I180_1` | % (0–100) | Suppression Ratio, Left Hemisphere | BSR Left Hemisphere_avg | P-DOC |
| `suppression_left_anterior` | `I179_1` | % (0–100) | Suppression Ratio, Left Anterior | BSR Left Anterior_avg | P-DOC |
| `suppression_left_posterior` | `I181_1` | % (0–100) | Suppression Ratio, Left Posterior | BSR Left Posterior_avg | P-DOC |
| `suppression_posterior` | `I186_1` | % (0–100) | Suppression Ratio, Posterior | BSR Posterior_avg | P-DOC |
| `suppression_right` | `I183_1` | % (0–100) | Suppression Ratio, Right Hemisphere | BSR Right Hemisphere_avg | P-DOC |
| `suppression_right_anterior` | `I182_1` | % (0–100) | Suppression Ratio, Right Anterior | BSR Right Anterior_avg | P-DOC |
| `suppression_right_posterior` | `I184_1` | % (0–100) | Suppression Ratio, Right Posterior | BSR Right Posterior_avg | P-DOC |

---

*Generated by `scripts/gen_column_map_md.py` from the CSV. Regenerate both with `gen_column_map_v10.py` first.*
