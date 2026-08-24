# Column map — Full Research Panel

**4,106 columns** across 27 families, generated from the shipped template through the production resolution path, so it cannot drift from what ingestion does.

Full record (all 34 fields per column): [`COLUMN_MAP_V10_FULL_RESEARCH_PANEL.csv`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.csv) · [`.json`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.json). The `.html` alongside them is a richer browser view, but GitHub will not render it — clone the repo and open it locally.

## Evidence tiers

Every column carries one. Read it before relying on the column.

| Tier | Meaning | Count |
|---|---|---:|
| `P-COMM` | direct Persyst communication | 2,188 |
| `P-DOC` | vendor-documented | 1,520 |
| `MMX` | read from the template | 391 |
| `EMP` | empirical / inferred — provisional | 7 |

## Families

| Family | Columns | Units |
|---|---:|---|
| [`adr`](#adr) | 42 | ratio of µV amplitudes (dimensionless); clamped at Ratio … |
| [`aeeg`](#aeeg) | 25 | µV (peak-to-peak) |
| [`alpha_variability`](#alpha-variability) | 27 | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless);… |
| [`annotation`](#annotation) | 1 | text |
| [`artifact_detector`](#artifact-detector) | 18 |  **— discarded at ingestion, never exported** |
| [`artifact_intensity`](#artifact-intensity) | 3 | muscle: µV (per Persyst 2026-08-20; help text says µV² — … |
| [`asymmetry`](#asymmetry) | 333 | % (EASI 0–100 magnitude; REASI −100 to +100, + = right>left) *(bins summarised below)* |
| [`coherence_spectrogram`](#coherence-spectrogram) | 320 | coherence (0–1) *(bins summarised below)* |
| [`electrode_quality`](#electrode-quality) | 22 | dimensionless, 0=clean → 1.0; >1.0 = above impedance disc… |
| [`fft_power`](#fft-power) | 82 | µV (amplitude; MMX PowerType=1 — NOT µV² power) |
| [`fft_spectrogram`](#fft-spectrogram) | 1,000 | µV/√Hz (amplitude spectral density = √(µV²/Hz); Persyst l… *(bins summarised below)* |
| [`heart_rate`](#heart-rate) | 2 | bpm |
| [`other`](#other) | 1 |  |
| [`peak_envelope`](#peak-envelope) | 9 | µV |
| [`rda`](#rda) | 3 | rhythmicity index |
| [`relative_power`](#relative-power) | 36 | band/broadband ratio of µV amplitudes (dimensionless); cl… |
| [`rhythmic_delta`](#rhythmic-delta) | 6 | boolean (0/1) |
| [`rhythmicity`](#rhythmicity) | 2,117 | rhythmicity index *(bins summarised below)* |
| [`seizure_burden`](#seizure-burden) | 2 | % (0–100) or category code per variant |
| [`seizure_detection`](#seizure-detection) | 4 | boolean (0/1) |
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
| `adr_all` | `I140_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, All 10-20 | FFT_PowerRatio 8-13//1-4 All 10-20_avg | P-DOC |
| `adr_anterior` | `I141_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Anterior | FFT_PowerRatio 8-13//1-4 Anterior_avg | P-DOC |
| `adr_avg_f3c3p3` | `I2_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz F3C3P3 (Blue) F… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 F3C3P3_avg] | P-DOC |
| `adr_avg_f4c4p4` | `I1_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz F3C3P3 (Blue) .… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 F4C4P4_avg] | P-DOC |
| `adr_avg_f7t7p7` | `I4_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz F7T7P7 (Blue) F… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 F7T7P7_avg] | P-DOC |
| `adr_avg_f8t8p8` | `I3_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz F7T7P7 (Blue) .… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 F8T8P8_avg] | P-DOC |
| `adr_avg_left_anterior` | `I5_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Anterior (… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Left Anterior_avg] | P-DOC |
| `adr_avg_left_hemisphere` | `I7_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Hemisphere… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Left Hemisphere_avg] | P-DOC |
| `adr_avg_left_posterior` | `I9_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Posterior … | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Left Posterior_avg] | P-DOC |
| `adr_avg_p3p7o1` | `I12_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz P3P7O1 (Blue) P… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 P3P7O1_avg] | P-DOC |
| `adr_avg_p4p8o2` | `I11_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz P3P7O1 (Blue) .… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 P4P8O2_avg] | P-DOC |
| `adr_avg_right_anterior` | `I6_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Anterior (… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Right Anterior_avg] | P-DOC |
| `adr_avg_right_hemisphere` | `I8_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Hemisphere… | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Right Hemisphere_avg] | P-DOC |
| `adr_avg_right_posterior` | `I10_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | ADR (2 min. running ave.) FFT PowerRatio 8-13/1-4Hz Left Posterior … | Time Avg <0,120> [FFT_PowerRatio 8-13//1-4 Right Posterior_avg] | P-DOC |
| `adr_f3c3p3` | `I142_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, F3C3P3 | FFT_PowerRatio 8-13//1-4 F3C3P3_avg | P-DOC |
| `adr_f4c4p4` | `I143_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, F4C4P4 | FFT_PowerRatio 8-13//1-4 F4C4P4_avg | P-DOC |
| `adr_f7t7p7` | `I144_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, F7T7P7 | FFT_PowerRatio 8-13//1-4 F7T7P7_avg | P-DOC |
| `adr_f8t8p8` | `I145_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, F8T8P8 | FFT_PowerRatio 8-13//1-4 F8T8P8_avg | P-DOC |
| `adr_left_anterior` | `I146_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Anterior | FFT_PowerRatio 8-13//1-4 Left Anterior_avg | P-DOC |
| `adr_left_hemisphere` | `I147_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Hemisphere | FFT_PowerRatio 8-13//1-4 Left Hemisphere_avg | P-DOC |
| `adr_left_posterior` | `I148_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Left Posterior | FFT_PowerRatio 8-13//1-4 Left Posterior_avg | P-DOC |
| `adr_p3p7o1` | `I149_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, P3P7O1 | FFT_PowerRatio 8-13//1-4 P3P7O1_avg | P-DOC |
| `adr_p4p8o2` | `I150_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, P4P8O2 | FFT_PowerRatio 8-13//1-4 P4P8O2_avg | P-DOC |
| `adr_posterior` | `I151_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Posterior | FFT_PowerRatio 8-13//1-4 Posterior_avg | P-DOC |
| `adr_right_anterior` | `I152_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Anterior | FFT_PowerRatio 8-13//1-4 Right Anterior_avg | P-DOC |
| `adr_right_hemisphere` | `I153_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Hemisphere | FFT_PowerRatio 8-13//1-4 Right Hemisphere_avg | P-DOC |
| `adr_right_posterior` | `I154_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 8-13/1-4 Hz, Right Posterior | FFT_PowerRatio 8-13//1-4 Right Posterior_avg | P-DOC |
| `tdr_all` | `I110_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, All 10-20 | FFT_PowerRatio 4-8//1-4 All 10-20_avg | P-DOC |
| `tdr_anterior` | `I111_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Anterior | FFT_PowerRatio 4-8//1-4 Anterior_avg | P-DOC |
| `tdr_f3c3p3` | `I112_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, F3C3P3 | FFT_PowerRatio 4-8//1-4 F3C3P3_avg | P-DOC |
| `tdr_f4c4p4` | `I113_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, F4C4P4 | FFT_PowerRatio 4-8//1-4 F4C4P4_avg | P-DOC |
| `tdr_f7t7p7` | `I114_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, F7T7P7 | FFT_PowerRatio 4-8//1-4 F7T7P7_avg | P-DOC |
| `tdr_f8t8p8` | `I115_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, F8T8P8 | FFT_PowerRatio 4-8//1-4 F8T8P8_avg | P-DOC |
| `tdr_left_anterior` | `I116_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Anterior | FFT_PowerRatio 4-8//1-4 Left Anterior_avg | P-DOC |
| `tdr_left_hemisphere` | `I117_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Hemisphere | FFT_PowerRatio 4-8//1-4 Left Hemisphere_avg | P-DOC |
| `tdr_left_posterior` | `I118_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Left Posterior | FFT_PowerRatio 4-8//1-4 Left Posterior_avg | P-DOC |
| `tdr_p3p7o1` | `I119_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, P3P7O1 | FFT_PowerRatio 4-8//1-4 P3P7O1_avg | P-DOC |
| `tdr_p4p8o2` | `I120_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, P4P8O2 | FFT_PowerRatio 4-8//1-4 P4P8O2_avg | P-DOC |
| `tdr_posterior` | `I121_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Posterior | FFT_PowerRatio 4-8//1-4 Posterior_avg | P-DOC |
| `tdr_right_anterior` | `I122_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Anterior | FFT_PowerRatio 4-8//1-4 Right Anterior_avg | P-DOC |
| `tdr_right_hemisphere` | `I123_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Hemisphere | FFT_PowerRatio 4-8//1-4 Right Hemisphere_avg | P-DOC |
| `tdr_right_posterior` | `I124_1` | ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NO… | FFT PowerRatio, 4-8/1-4 Hz, Right Posterior | FFT_PowerRatio 4-8//1-4 Right Posterior_avg | P-DOC |

### aeeg

**Units:** µV (peak-to-peak)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `aeeg_anterior_max` | `I14_1` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_min` | `I14_2` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p25` | `I14_5` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p50` | `I14_3` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_anterior_p75` | `I14_4` | µV (peak-to-peak) | aEEG, Anterior | aEEG Anterior_avg | P-COMM |
| `aeeg_left_max` | `I15_1` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_min` | `I15_2` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p25` | `I15_5` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p50` | `I15_3` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_left_p75` | `I15_4` | µV (peak-to-peak) | aEEG, Left Hemisphere | aEEG Left Hemisphere_avg | P-COMM |
| `aeeg_max` | `I13_1` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_min` | `I13_2` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p25` | `I13_5` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p50` | `I13_3` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_p75` | `I13_4` | µV (peak-to-peak) | aEEG, All 10-20 | aEEG All 10-20_avg | P-COMM |
| `aeeg_posterior_max` | `I16_1` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_min` | `I16_2` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p25` | `I16_5` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p50` | `I16_3` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_posterior_p75` | `I16_4` | µV (peak-to-peak) | aEEG, Posterior | aEEG Posterior_avg | P-COMM |
| `aeeg_right_max` | `I17_1` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_min` | `I17_2` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p25` | `I17_5` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p50` | `I17_3` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |
| `aeeg_right_p75` | `I17_4` | µV (peak-to-peak) | aEEG, Right Hemisphere | aEEG Right Hemisphere_avg | P-COMM |

### alpha_variability

**Units:** RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rav_all` | `I125_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, All 10-20 | FFT_PowerRatio 6-14//1-20 All 10-20_avg | MMX |
| `rav_anterior` | `I126_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Anterior | FFT_PowerRatio 6-14//1-20 Anterior_avg | MMX |
| `rav_avg_f3c3p3` | `I191_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz F3C3P3, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 F3C3P3_avg] | MMX |
| `rav_avg_f4c4p4` | `I192_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz F4C4P4, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 F4C4P4_avg] | MMX |
| `rav_avg_f7t7p7` | `I193_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz F7T7P7, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 F7T7P7_avg] | MMX |
| `rav_avg_f8t8p8` | `I194_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz F8T8P8, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 F8T8P8_avg] | MMX |
| `rav_avg_left_anterior` | `I195_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Anterior,… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Anterior_avg] | MMX |
| `rav_avg_left_hemisphere` | `I196_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Hemispher… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Hemisphere_avg] | MMX |
| `rav_avg_left_posterior` | `I197_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Left Posterior… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Left Posterior_avg] | MMX |
| `rav_avg_p3p7o1` | `I198_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz P3P7O1, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 P3P7O1_avg] | MMX |
| `rav_avg_p4p8o2` | `I199_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz P4P8O2, FFT Po… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 P4P8O2_avg] | MMX |
| `rav_avg_right_anterior` | `I200_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Anterior… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Anterior_avg] | MMX |
| `rav_avg_right_hemisphere` | `I201_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Hemisphe… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Hemisphere_avg] | MMX |
| `rav_avg_right_posterior` | `I202_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | RAV (2 min. running ave.) FFT PowerRatio 6-14/1-20Hz Right Posterio… | Time Avg <0,120> [FFT_PowerRatio 6-14//1-20 Right Posterior_avg] | MMX |
| `rav_f3c3p3` | `I127_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, F3C3P3 | FFT_PowerRatio 6-14//1-20 F3C3P3_avg | MMX |
| `rav_f4c4p4` | `I128_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, F4C4P4 | FFT_PowerRatio 6-14//1-20 F4C4P4_avg | MMX |
| `rav_f7t7p7` | `I129_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, F7T7P7 | FFT_PowerRatio 6-14//1-20 F7T7P7_avg | MMX |
| `rav_f8t8p8` | `I130_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, F8T8P8 | FFT_PowerRatio 6-14//1-20 F8T8P8_avg | MMX |
| `rav_left_anterior` | `I131_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Anterior | FFT_PowerRatio 6-14//1-20 Left Anterior_avg | MMX |
| `rav_left_hemisphere` | `I132_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Hemisphere | FFT_PowerRatio 6-14//1-20 Left Hemisphere_avg | MMX |
| `rav_left_posterior` | `I133_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Left Posterior | FFT_PowerRatio 6-14//1-20 Left Posterior_avg | MMX |
| `rav_p3p7o1` | `I134_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, P3P7O1 | FFT_PowerRatio 6-14//1-20 P3P7O1_avg | MMX |
| `rav_p4p8o2` | `I135_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, P4P8O2 | FFT_PowerRatio 6-14//1-20 P4P8O2_avg | MMX |
| `rav_posterior` | `I136_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Posterior | FFT_PowerRatio 6-14//1-20 Posterior_avg | MMX |
| `rav_right_anterior` | `I137_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Anterior | FFT_PowerRatio 6-14//1-20 Right Anterior_avg | MMX |
| `rav_right_hemisphere` | `I138_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Hemisphere | FFT_PowerRatio 6-14//1-20 Right Hemisphere_avg | MMX |
| `rav_right_posterior` | `I139_1` | RAV: 6–14/1–20 Hz ratio of µV amplitudes (dimensionless); clamped a… | FFT PowerRatio, 6-14/1-20 Hz, Right Posterior | FFT_PowerRatio 6-14//1-20 Right Posterior_avg | MMX |

### annotation

**Units:** text

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `annotation` | `I371_1` | text | Comment |  | P-DOC |

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
| `artifact_intensity_emg` | `I19_1` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |
| `artifact_intensity_eye_horizontal` | `I19_3` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |
| `artifact_intensity_eye_vertical` | `I19_2` | muscle: µV (per Persyst 2026-08-20; help text says µV² — unconfirme… | Artifact Intensity | ArtifactIntensity | P-COMM |

### asymmetry

**Units:** % (EASI 0–100 magnitude; REASI −100 to +100, + = right>left)

333 columns — one per frequency bin, across 21 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `asymmetry_easi_broadband_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_anterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_parasagittal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_posterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_alpha_temporal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_broadband_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_anterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_parasagittal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_posterior` | 1 | — | `P-DOC` |
| `asymmetry_reasi_delta_temporal` | 1 | — | `P-DOC` |
| `asymmetry_reasi_hemisphere` | 1 | — | `P-DOC` |
| `asymmetry_spec_anterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_f3c3p3` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_f7t7p7` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_hemi` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_p3p7o1` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_parasagittal` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_posterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `asymmetry_spec_temporal` | 40 | 0.5–20 Hz | `P-DOC` |

### coherence_spectrogram

**Units:** coherence (0–1)

320 columns — one per frequency bin, across 10 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `coherence_avg_c3p3` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_f3c3` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_p3o1` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_p7o1` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_avg_t7p7` | 1 | 0.32–0.32 Hz | `MMX` |
| `coherence_spec_c3p3` | 63 | 0–32 Hz | `MMX` |
| `coherence_spec_f3c3` | 63 | 0–32 Hz | `MMX` |
| `coherence_spec_p3o1` | 63 | 0–32 Hz | `MMX` |
| `coherence_spec_p7o1` | 63 | 0–32 Hz | `MMX` |
| `coherence_spec_t7p7` | 63 | 0–32 Hz | `MMX` |

### electrode_quality

**Units:** dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect threshold. Clamped at the MMX display Maximum (1.2 in this template)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `esq_ch01` | `I55_1` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch02` | `I55_2` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch03` | `I55_3` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch04` | `I55_4` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch05` | `I55_5` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch06` | `I55_6` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch07` | `I55_7` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch08` | `I55_8` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch09` | `I55_9` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch10` | `I55_10` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch11` | `I55_11` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch12` | `I55_12` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch13` | `I55_13` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch14` | `I55_14` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch15` | `I55_15` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch16` | `I55_16` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch17` | `I55_17` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch18` | `I55_18` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch19` | `I55_19` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch20` | `I55_20` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch21` | `I55_21` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |
| `esq_ch22` | `I55_22` | dimensionless, 0=clean → 1.0; >1.0 = above impedance disconnect thr… | Electrode Signal Quality | ElectrodeSignalQuality | P-COMM |

### fft_power

**Units:** µV (amplitude; MMX PowerType=1 — NOT µV² power)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `fft_alpha_all` | `I101_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, All 10-20 | FFT_Power 8-13 All 10-20_avg | P-DOC |
| `fft_alpha_anterior` | `I102_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Anterior | FFT_Power 8-13 Anterior_avg | P-DOC |
| `fft_alpha_left_anterior` | `I103_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Anterior | FFT_Power 8-13 Left Anterior_avg | P-DOC |
| `fft_alpha_left_hemisphere` | `I104_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Hemisphere | FFT_Power 8-13 Left Hemisphere_avg | P-DOC |
| `fft_alpha_left_posterior` | `I105_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Left Posterior | FFT_Power 8-13 Left Posterior_avg | P-DOC |
| `fft_alpha_posterior` | `I106_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Posterior | FFT_Power 8-13 Posterior_avg | P-DOC |
| `fft_alpha_right_anterior` | `I107_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Anterior | FFT_Power 8-13 Right Anterior_avg | P-DOC |
| `fft_alpha_right_hemisphere` | `I108_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Hemisphere | FFT_Power 8-13 Right Hemisphere_avg | P-DOC |
| `fft_alpha_right_posterior` | `I109_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 8 - 13 Hz, Right Posterior | FFT_Power 8-13 Right Posterior_avg | P-DOC |
| `fft_avg2m_alpha_all` | `I351_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 8-13Hz, FFT Power, 8 - 13 Hz, All 10-20 | Time Avg <0,120> [FFT_Power 8-13 All 10-20_avg] | P-DOC |
| `fft_avg2m_alpha_left_hemisphere` | `I349_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 8-13Hz Left Hemisphere, FFT Power, 8 - 1… | Time Avg <0,120> [FFT_Power 8-13 Left Hemisphere_avg] | P-DOC |
| `fft_avg2m_alpha_right_hemisphere` | `I350_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 8-13Hz Right Hemisphere, FFT Power, 8 - … | Time Avg <0,120> [FFT_Power 8-13 Right Hemisphere_avg] | P-DOC |
| `fft_avg2m_beta_all` | `I342_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 13-20Hz, FFT Power, 13 - 20 Hz, All 10-20 | Time Avg <0,120> [FFT_Power 13-20 All 10-20_avg] | P-DOC |
| `fft_avg2m_beta_left_hemisphere` | `I340_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 13-20Hz Left Hemisphere, FFT Power, 13 -… | Time Avg <0,120> [FFT_Power 13-20 Left Hemisphere_avg] | P-DOC |
| `fft_avg2m_beta_right_hemisphere` | `I341_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 13-20Hz Right Hemisphere, FFT Power, 13 … | Time Avg <0,120> [FFT_Power 13-20 Right Hemisphere_avg] | P-DOC |
| `fft_avg2m_delta_all` | `I345_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 1-4Hz, FFT Power, 1 - 4 Hz, All 10-20 | Time Avg <0,120> [FFT_Power 1-4 All 10-20_avg] | P-DOC |
| `fft_avg2m_delta_left_hemisphere` | `I343_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 1-4Hz Left Hemisphere, FFT Power, 1 - 4 … | Time Avg <0,120> [FFT_Power 1-4 Left Hemisphere_avg] | P-DOC |
| `fft_avg2m_delta_right_hemisphere` | `I344_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 1-4Hz Right Hemisphere, FFT Power, 1 - 4… | Time Avg <0,120> [FFT_Power 1-4 Right Hemisphere_avg] | P-DOC |
| `fft_avg2m_theta_all` | `I348_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 4-8Hz, FFT Power, 4 - 8 Hz, All 10-20 | Time Avg <0,120> [FFT_Power 4-8 All 10-20_avg] | P-DOC |
| `fft_avg2m_theta_left_hemisphere` | `I346_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 4-8Hz Left Hemisphere, FFT Power, 4 - 8 … | Time Avg <0,120> [FFT_Power 4-8 Left Hemisphere_avg] | P-DOC |
| `fft_avg2m_theta_right_hemisphere` | `I347_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (2 min. running ave.) 4-8Hz Right Hemisphere, FFT Power, 4 - 8… | Time Avg <0,120> [FFT_Power 4-8 Right Hemisphere_avg] | P-DOC |
| `fft_avg64s_alpha_left_anterior` | `I364_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 8 - 13 Hz, Left Anterior | Time Avg <0,64> [FFT_Power 8-13 Left Anterior_avg] | P-DOC |
| `fft_avg64s_alpha_left_posterior` | `I365_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 8 - 13 Hz, Left Posterior | Time Avg <0,64> [FFT_Power 8-13 Left Posterior_avg] | P-DOC |
| `fft_avg64s_alpha_right_anterior` | `I366_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 8 - 13 Hz, Right Anterior | Time Avg <0,64> [FFT_Power 8-13 Right Anterior_avg] | P-DOC |
| `fft_avg64s_alpha_right_posterior` | `I367_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 8 - 13 Hz, Right Posterior | Time Avg <0,64> [FFT_Power 8-13 Right Posterior_avg] | P-DOC |
| `fft_avg64s_beta_left_anterior` | `I352_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 13 - 20 Hz, Left Anterior | Time Avg <0,64> [FFT_Power 13-20 Left Anterior_avg] | P-DOC |
| `fft_avg64s_beta_left_posterior` | `I353_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 13 - 20 Hz, Left Posterior | Time Avg <0,64> [FFT_Power 13-20 Left Posterior_avg] | P-DOC |
| `fft_avg64s_beta_right_anterior` | `I354_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 13 - 20 Hz, Right Anterior | Time Avg <0,64> [FFT_Power 13-20 Right Anterior_avg] | P-DOC |
| `fft_avg64s_beta_right_posterior` | `I355_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 13 - 20 Hz, Right Posterior | Time Avg <0,64> [FFT_Power 13-20 Right Posterior_avg] | P-DOC |
| `fft_avg64s_delta_left_anterior` | `I356_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 1 - 4 Hz, Left Anterior | Time Avg <0,64> [FFT_Power 1-4 Left Anterior_avg] | P-DOC |
| `fft_avg64s_delta_left_posterior` | `I357_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 1 - 4 Hz, Left Posterior | Time Avg <0,64> [FFT_Power 1-4 Left Posterior_avg] | P-DOC |
| `fft_avg64s_delta_right_anterior` | `I358_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 1 - 4 Hz, Right Anterior | Time Avg <0,64> [FFT_Power 1-4 Right Anterior_avg] | P-DOC |
| `fft_avg64s_delta_right_posterior` | `I359_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 1 - 4 Hz, Right Posterior | Time Avg <0,64> [FFT_Power 1-4 Right Posterior_avg] | P-DOC |
| `fft_avg64s_theta_left_anterior` | `I360_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 4 - 8 Hz, Left Anterior | Time Avg <0,64> [FFT_Power 4-8 Left Anterior_avg] | P-DOC |
| `fft_avg64s_theta_left_posterior` | `I361_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 4 - 8 Hz, Left Posterior | Time Avg <0,64> [FFT_Power 4-8 Left Posterior_avg] | P-DOC |
| `fft_avg64s_theta_right_anterior` | `I362_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 4 - 8 Hz, Right Anterior | Time Avg <0,64> [FFT_Power 4-8 Right Anterior_avg] | P-DOC |
| `fft_avg64s_theta_right_posterior` | `I363_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | Time (64 sec running ave), FFT Power, 4 - 8 Hz, Right Posterior | Time Avg <0,64> [FFT_Power 4-8 Right Posterior_avg] | P-DOC |
| `fft_beta_all` | `I74_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, All 10-20 | FFT_Power 13-20 All 10-20_avg | P-DOC |
| `fft_beta_anterior` | `I75_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Anterior | FFT_Power 13-20 Anterior_avg | P-DOC |
| `fft_beta_left_anterior` | `I76_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Anterior | FFT_Power 13-20 Left Anterior_avg | P-DOC |
| `fft_beta_left_hemisphere` | `I77_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Hemisphere | FFT_Power 13-20 Left Hemisphere_avg | P-DOC |
| `fft_beta_left_posterior` | `I78_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Left Posterior | FFT_Power 13-20 Left Posterior_avg | P-DOC |
| `fft_beta_posterior` | `I79_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Posterior | FFT_Power 13-20 Posterior_avg | P-DOC |
| `fft_beta_right_anterior` | `I80_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Anterior | FFT_Power 13-20 Right Anterior_avg | P-DOC |
| `fft_beta_right_hemisphere` | `I81_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Hemisphere | FFT_Power 13-20 Right Hemisphere_avg | P-DOC |
| `fft_beta_right_posterior` | `I82_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 20 Hz, Right Posterior | FFT_Power 13-20 Right Posterior_avg | P-DOC |
| `fft_beta_wide_all` | `I83_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, All 10-20 | FFT_Power 13-30 All 10-20_avg | P-DOC |
| `fft_beta_wide_anterior` | `I84_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Anterior | FFT_Power 13-30 Anterior_avg | P-DOC |
| `fft_beta_wide_left_anterior` | `I85_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Anterior | FFT_Power 13-30 Left Anterior_avg | P-DOC |
| `fft_beta_wide_left_hemisphere` | `I86_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Hemisphere | FFT_Power 13-30 Left Hemisphere_avg | P-DOC |
| `fft_beta_wide_left_posterior` | `I87_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Left Posterior | FFT_Power 13-30 Left Posterior_avg | P-DOC |
| `fft_beta_wide_posterior` | `I88_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Posterior | FFT_Power 13-30 Posterior_avg | P-DOC |
| `fft_beta_wide_right_anterior` | `I89_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Anterior | FFT_Power 13-30 Right Anterior_avg | P-DOC |
| `fft_beta_wide_right_hemisphere` | `I90_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Hemisphere | FFT_Power 13-30 Right Hemisphere_avg | P-DOC |
| `fft_beta_wide_right_posterior` | `I91_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 13 - 30 Hz, Right Posterior | FFT_Power 13-30 Right Posterior_avg | P-DOC |
| `fft_delta_all` | `I65_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, All 10-20 | FFT_Power 1-4 All 10-20_avg | P-DOC |
| `fft_delta_anterior` | `I66_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Anterior | FFT_Power 1-4 Anterior_avg | P-DOC |
| `fft_delta_left_anterior` | `I67_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Anterior | FFT_Power 1-4 Left Anterior_avg | P-DOC |
| `fft_delta_left_hemisphere` | `I68_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Hemisphere | FFT_Power 1-4 Left Hemisphere_avg | P-DOC |
| `fft_delta_left_posterior` | `I69_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Left Posterior | FFT_Power 1-4 Left Posterior_avg | P-DOC |
| `fft_delta_posterior` | `I70_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Posterior | FFT_Power 1-4 Posterior_avg | P-DOC |
| `fft_delta_right_anterior` | `I71_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Anterior | FFT_Power 1-4 Right Anterior_avg | P-DOC |
| `fft_delta_right_hemisphere` | `I72_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Hemisphere | FFT_Power 1-4 Right Hemisphere_avg | P-DOC |
| `fft_delta_right_posterior` | `I73_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 4 Hz, Right Posterior | FFT_Power 1-4 Right Posterior_avg | P-DOC |
| `fft_power_all` | `I56_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, All 10-20 | FFT_Power 1-20 All 10-20_avg | P-DOC |
| `fft_power_anterior` | `I57_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Anterior | FFT_Power 1-20 Anterior_avg | P-DOC |
| `fft_power_left_anterior` | `I58_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Anterior | FFT_Power 1-20 Left Anterior_avg | P-DOC |
| `fft_power_left_hemisphere` | `I59_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Hemisphere | FFT_Power 1-20 Left Hemisphere_avg | P-DOC |
| `fft_power_left_posterior` | `I60_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Left Posterior | FFT_Power 1-20 Left Posterior_avg | P-DOC |
| `fft_power_posterior` | `I61_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Posterior | FFT_Power 1-20 Posterior_avg | P-DOC |
| `fft_power_right_anterior` | `I62_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Anterior | FFT_Power 1-20 Right Anterior_avg | P-DOC |
| `fft_power_right_hemisphere` | `I63_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Hemisphere | FFT_Power 1-20 Right Hemisphere_avg | P-DOC |
| `fft_power_right_posterior` | `I64_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 1 - 20 Hz, Right Posterior | FFT_Power 1-20 Right Posterior_avg | P-DOC |
| `fft_theta_all` | `I92_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, All 10-20 | FFT_Power 4-8 All 10-20_avg | P-DOC |
| `fft_theta_anterior` | `I93_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Anterior | FFT_Power 4-8 Anterior_avg | P-DOC |
| `fft_theta_left_anterior` | `I94_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Anterior | FFT_Power 4-8 Left Anterior_avg | P-DOC |
| `fft_theta_left_hemisphere` | `I95_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Hemisphere | FFT_Power 4-8 Left Hemisphere_avg | P-DOC |
| `fft_theta_left_posterior` | `I96_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Left Posterior | FFT_Power 4-8 Left Posterior_avg | P-DOC |
| `fft_theta_posterior` | `I97_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Posterior | FFT_Power 4-8 Posterior_avg | P-DOC |
| `fft_theta_right_anterior` | `I98_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Anterior | FFT_Power 4-8 Right Anterior_avg | P-DOC |
| `fft_theta_right_hemisphere` | `I99_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Hemisphere | FFT_Power 4-8 Right Hemisphere_avg | P-DOC |
| `fft_theta_right_posterior` | `I100_1` | µV (amplitude; MMX PowerType=1 — NOT µV² power) | FFT Power, 4 - 8 Hz, Right Posterior | FFT_Power 4-8 Right Posterior_avg | P-DOC |

### fft_spectrogram

**Units:** µV/√Hz (amplitude spectral density = √(µV²/Hz); Persyst label 'sqrt(µV)/Hz'; square to get PSD µV²/Hz)

1,000 columns — one per frequency bin, across 25 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `fft_spec` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_c3p3` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_c4p4` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_czpz` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_f3c3` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_f4c4` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_f7t7` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_f8t8` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_fp1f3` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_fp1f7` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_fp2f4` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_fp2f8` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_fzcz` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_left_anterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_left_hemisphere` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_left_posterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_p3o1` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_p4o2` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_p7o1` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_p8o2` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_right_anterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_right_hemisphere` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_right_posterior` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_t7p7` | 40 | 0.5–20 Hz | `P-DOC` |
| `fft_spec_t8p8` | 40 | 0.5–20 Hz | `P-DOC` |

### heart_rate

**Units:** bpm

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `heart_rate` | `I180_1` | bpm | Heart Rate 1 | Heart Rate | P-DOC |
| `heart_rate_2` | `I181_1` | bpm | Heart Rate 2 | Heart Rate01 | P-DOC |

### other

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `other_i372s1` | `I372_1` |  | Time |  | EMP |

### peak_envelope

**Units:** µV

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `peak_envelope` | `I182_1` | µV | PeakEnvelope, 2 - 20 Hz, All 10-20 | PeakEnvelope 2-20 All 10-20_avg | P-DOC |
| `peak_envelope_anterior` | `I183_1` | µV | PeakEnvelope, 2 - 20 Hz, Anterior | PeakEnvelope 2-20 Anterior_avg | P-DOC |
| `peak_envelope_left_anterior` | `I184_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Anterior | PeakEnvelope 2-20 Left Anterior_avg | P-DOC |
| `peak_envelope_left_hemisphere` | `I185_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Hemisphere | PeakEnvelope 2-20 Left Hemisphere_avg | P-DOC |
| `peak_envelope_left_posterior` | `I186_1` | µV | PeakEnvelope, 2 - 20 Hz, Left Posterior | PeakEnvelope 2-20 Left Posterior_avg | P-DOC |
| `peak_envelope_posterior` | `I187_1` | µV | PeakEnvelope, 2 - 20 Hz, Posterior | PeakEnvelope 2-20 Posterior_avg | P-DOC |
| `peak_envelope_right_anterior` | `I188_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Anterior | PeakEnvelope 2-20 Right Anterior_avg | P-DOC |
| `peak_envelope_right_hemisphere` | `I189_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Hemisphere | PeakEnvelope 2-20 Right Hemisphere_avg | P-DOC |
| `peak_envelope_right_posterior` | `I190_1` | µV | PeakEnvelope, 2 - 20 Hz, Right Posterior | PeakEnvelope 2-20 Right Posterior_avg | P-DOC |

### rda

**Units:** rhythmicity index

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rda_bilateral` | `I240_1` | rhythmicity index | Rhythmic delta indicator bilateral(blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left… | P-COMM |
| `rda_left` | `I239_1` | rhythmicity index | Rhythmic delta indicator left (blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left… | P-COMM |
| `rda_right` | `I241_1` | rhythmicity index | Rhythmic delta indicator right (blue=left, red=right, green=gen) | [[[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Righ… | P-COMM |

### relative_power

**Units:** band/broadband ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. NOT conventional relative power (band power ÷ total power) — equals its square root.

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rel_alpha_all` | `I203_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, All 10-20 | FFT_PowerRatio 8-13//1-30 All 10-20_avg | MMX |
| `rel_alpha_anterior` | `I204_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Anterior | FFT_PowerRatio 8-13//1-30 Anterior_avg | MMX |
| `rel_alpha_left_anterior` | `I205_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Anterior | FFT_PowerRatio 8-13//1-30 Left Anterior_avg | MMX |
| `rel_alpha_left_hemisphere` | `I206_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Hemisphere | FFT_PowerRatio 8-13//1-30 Left Hemisphere_avg | MMX |
| `rel_alpha_left_posterior` | `I207_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Left Posterior | FFT_PowerRatio 8-13//1-30 Left Posterior_avg | MMX |
| `rel_alpha_posterior` | `I208_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Posterior | FFT_PowerRatio 8-13//1-30 Posterior_avg | MMX |
| `rel_alpha_right_anterior` | `I209_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Anterior | FFT_PowerRatio 8-13//1-30 Right Anterior_avg | MMX |
| `rel_alpha_right_hemisphere` | `I210_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Hemisphere | FFT_PowerRatio 8-13//1-30 Right Hemisphere_avg | MMX |
| `rel_alpha_right_posterior` | `I211_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Alpha, 8-13/1-30 Hz, Right Posterior | FFT_PowerRatio 8-13//1-30 Right Posterior_avg | MMX |
| `rel_beta_wide_all` | `I212_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, All 10-20 | FFT_PowerRatio 13-30//1-30 All 10-20_avg | MMX |
| `rel_beta_wide_anterior` | `I213_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Anterior | FFT_PowerRatio 13-30//1-30 Anterior_avg | MMX |
| `rel_beta_wide_left_anterior` | `I214_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Anterior | FFT_PowerRatio 13-30//1-30 Left Anterior_avg | MMX |
| `rel_beta_wide_left_hemisphere` | `I215_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Hemisphere | FFT_PowerRatio 13-30//1-30 Left Hemisphere_avg | MMX |
| `rel_beta_wide_left_posterior` | `I216_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Left Posterior | FFT_PowerRatio 13-30//1-30 Left Posterior_avg | MMX |
| `rel_beta_wide_posterior` | `I217_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Posterior | FFT_PowerRatio 13-30//1-30 Posterior_avg | MMX |
| `rel_beta_wide_right_anterior` | `I218_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Anterior | FFT_PowerRatio 13-30//1-30 Right Anterior_avg | MMX |
| `rel_beta_wide_right_hemisphere` | `I219_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Hemisphere | FFT_PowerRatio 13-30//1-30 Right Hemisphere_avg | MMX |
| `rel_beta_wide_right_posterior` | `I220_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Beta, 13-30/1-30 Hz, Right Posterior | FFT_PowerRatio 13-30//1-30 Right Posterior_avg | MMX |
| `rel_delta_all` | `I221_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, All 10-20 | FFT_PowerRatio 1-4//1-30 All 10-20_avg | MMX |
| `rel_delta_anterior` | `I222_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Anterior | FFT_PowerRatio 1-4//1-30 Anterior_avg | MMX |
| `rel_delta_left_anterior` | `I223_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Anterior | FFT_PowerRatio 1-4//1-30 Left Anterior_avg | MMX |
| `rel_delta_left_hemisphere` | `I224_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Hemisphere | FFT_PowerRatio 1-4//1-30 Left Hemisphere_avg | MMX |
| `rel_delta_left_posterior` | `I225_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Left Posterior | FFT_PowerRatio 1-4//1-30 Left Posterior_avg | MMX |
| `rel_delta_posterior` | `I226_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Posterior | FFT_PowerRatio 1-4//1-30 Posterior_avg | MMX |
| `rel_delta_right_anterior` | `I227_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Anterior | FFT_PowerRatio 1-4//1-30 Right Anterior_avg | MMX |
| `rel_delta_right_hemisphere` | `I228_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Hemisphere | FFT_PowerRatio 1-4//1-30 Right Hemisphere_avg | MMX |
| `rel_delta_right_posterior` | `I229_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Delta, 1-4/1-30 Hz, Right Posterior | FFT_PowerRatio 1-4//1-30 Right Posterior_avg | MMX |
| `rel_theta_all` | `I230_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, All 10-20 | FFT_PowerRatio 4-8//1-30 All 10-20_avg | MMX |
| `rel_theta_anterior` | `I231_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Anterior | FFT_PowerRatio 4-8//1-30 Anterior_avg | MMX |
| `rel_theta_left_anterior` | `I232_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Anterior | FFT_PowerRatio 4-8//1-30 Left Anterior_avg | MMX |
| `rel_theta_left_hemisphere` | `I233_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Hemisphere | FFT_PowerRatio 4-8//1-30 Left Hemisphere_avg | MMX |
| `rel_theta_left_posterior` | `I234_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Left Posterior | FFT_PowerRatio 4-8//1-30 Left Posterior_avg | MMX |
| `rel_theta_posterior` | `I235_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Posterior | FFT_PowerRatio 4-8//1-30 Posterior_avg | MMX |
| `rel_theta_right_anterior` | `I236_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Anterior | FFT_PowerRatio 4-8//1-30 Right Anterior_avg | MMX |
| `rel_theta_right_hemisphere` | `I237_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Hemisphere | FFT_PowerRatio 4-8//1-30 Right Hemisphere_avg | MMX |
| `rel_theta_right_posterior` | `I238_1` | band/broadband ratio of µV amplitudes (dimensionless); clamped at R… | Relative Theta, 4-8/1-30 Hz, Right Posterior | FFT_PowerRatio 4-8//1-30 Right Posterior_avg | MMX |

### rhythmic_delta

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `rhythmic_delta_left_anterior` | `I39_1` | boolean (0/1) | Boolean LAD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left A… | EMP |
| `rhythmic_delta_left_hemisphere` | `I41_1` | boolean (0/1) | Boolean LRD+ | [[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left … | EMP |
| `rhythmic_delta_left_posterior` | `I40_1` | boolean (0/1) | Boolean LPD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left P… | EMP |
| `rhythmic_delta_right_anterior` | `I42_1` | boolean (0/1) | Boolean RAD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right … | EMP |
| `rhythmic_delta_right_hemisphere` | `I44_1` | boolean (0/1) | Boolean RRD+ | [[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right… | EMP |
| `rhythmic_delta_right_posterior` | `I43_1` | boolean (0/1) | Boolean RPD+ | [>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Right … | EMP |

### rhythmicity

**Units:** rhythmicity index

2,117 columns — one per frequency bin, across 101 instruments. Bin names follow `<stem>_<centre-frequency>hz` with the decimal written as `_`, so the frequency is readable from the slug. Listed by instrument; the individual bins are in the CSV.

| Instrument | Bins | Frequency range | Tier |
|---|---:|---|---|
| `rhythmicity` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_c3p3` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_c4p4` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_czpz` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_f3c3` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_f4c4` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_f7t7` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_f8t8` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_fp1f3` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_fp1f7` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_fp2f4` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_fp2f8` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_16_25hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_16_25hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_16_25hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_16_25hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_1_4hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_1_4hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_1_4hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_1_4hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_4_9hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_4_9hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_4_9hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_4_9hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_9_16hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_9_16hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_9_16hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_anterior_9_16hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_16_25hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_16_25hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_16_25hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_16_25hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_1_4hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_1_4hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_1_4hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_1_4hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_4_9hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_4_9hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_4_9hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_4_9hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_9_16hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_9_16hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_9_16hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_left_posterior_9_16hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_16_25hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_16_25hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_16_25hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_16_25hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_1_4hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_1_4hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_1_4hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_1_4hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_4_9hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_4_9hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_4_9hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_4_9hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_9_16hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_9_16hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_9_16hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_anterior_9_16hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_16_25hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_16_25hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_16_25hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_16_25hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_1_4hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_1_4hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_1_4hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_1_4hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_4_9hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_4_9hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_4_9hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_4_9hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_9_16hz_bandwidth` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_9_16hz_fraction` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_9_16hz_freq` | 1 | — | `P-COMM` |
| `rhythmicity_freqpow_right_posterior_9_16hz_power` | 1 | — | `P-COMM` |
| `rhythmicity_fzcz` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_left_hemisphere` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_p3o1` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_p4o2` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_p7o1` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_p8o2` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_right_hemisphere` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_sum_left_anterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_anterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_posterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_left_posterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_anterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_anterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_posterior_delta_freq` | 1 | — | `P-COMM` |
| `rhythmicity_sum_right_posterior_delta_power` | 1 | — | `P-COMM` |
| `rhythmicity_t7p7` | 97 | 1–25 Hz | `P-COMM` |
| `rhythmicity_t8p8` | 97 | 1–25 Hz | `P-COMM` |
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
| `seizure_burden_persyst_category` | `I280_1` | % (0–100) or category code per variant | Seizure Burden - 5 min- Category | Seizure Burden01 | MMX |
| `seizure_burden_persyst_percentage` | `I279_1` | % (0–100) or category code per variant | Seizure Burden - 5 min - Percentage | Seizure Burden | MMX |

### seizure_detection

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_detection_event` | `I281_1` | boolean (0/1) | Seizure Detections (red) and Notifications (gray) | SeizureEventsP14 | P-DOC |
| `seizure_detection_p14` | `I284_1` | boolean (0/1) | Seizure detections | SeizureProbabilityP14 Detections | P-DOC |
| `seizure_detection_p14_max120s` | `I368_1` | boolean (0/1) | Time, Seizure detections | Time Max <0,120> [SeizureProbabilityP14 Detections] | P-DOC |
| `seizure_notification_event` | `I281_2` | boolean (0/1) | Seizure Detections (red) and Notifications (gray) | SeizureEventsP14 | P-DOC |

### seizure_notification

**Units:** boolean (0/1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_notification_p14` | `I282_1` | boolean (0/1) | Seizure Notifications (P14) | SeizureProbabilityP14 Notifications | P-DOC |

### seizure_probability

**Units:** probability (0–1)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `seizure_probability_p14_probability` | `I283_1` | probability (0–1) | Seizure probability | SeizureProbabilityP14 Probability | P-DOC |

### sleep

**Units:** sleep stage code

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `sleep_stage_0` | `I291_1` | sleep stage code | Sleep-Wake Stage Indeterminate (yellow=wake; green-blue=N1; light b… | = 0 <0> [SleepStages] | P-DOC |
| `sleep_stage_1` | `I286_1` | sleep stage code | Sleep-Wake Stage N3 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 1 <0> [SleepStages] | P-DOC |
| `sleep_stage_2` | `I287_1` | sleep stage code | Sleep-Wake Stage N2 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 2 <0> [SleepStages] | P-DOC |
| `sleep_stage_3` | `I288_1` | sleep stage code | Sleep-Wake Stage N1 (yellow=wake; green-blue=N1; light blue=N2; dar… | = 3 <0> [SleepStages] | P-DOC |
| `sleep_stage_4` | `I289_1` | sleep stage code | Sleep-Wake Stage REM (yellow=wake; green-blue=N1; light blue=N2; da… | = 4 <0> [SleepStages] | P-DOC |
| `sleep_stage_5` | `I290_1` | sleep stage code | Sleep-Wake Stage Wake (yellow=wake; green-blue=N1; light blue=N2; d… | = 5 <0> [SleepStages] | P-DOC |
| `sleep_stage_display` | `I285_1` | sleep stage code | SleepStages | SleepStages | P-DOC |
| `sleep_wake_state` | `I292_1` | sleep stage code | Sleep-Wake State (yellow=wake; blue=sleep; black=indeterminate), [S… | ColorScaledBars | P-DOC |

### spectral_edge

**Units:** Hz

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `sef_50_all` | `I271_1` | Hz | SEF50, All 10-20 | FFT_Edge 50 0-32 All 10-20_avg | P-DOC |
| `sef_75_all` | `I272_1` | Hz | SEF75, All 10-20 | FFT_Edge 75 0-32 All 10-20_avg | P-DOC |
| `sef_90_all` | `I273_1` | Hz | SEF90, All 10-20 | FFT_Edge 90 0-32 All 10-20_avg | P-DOC |
| `sef_95_all` | `I274_1` | Hz | SEF95, All 10-20 | FFT_Edge 95 0-32 All 10-20_avg | P-DOC |
| `sef_95_anterior` | `I275_1` | Hz | SEF95, Anterior | FFT_Edge 95 0-32 Anterior_avg | P-DOC |
| `sef_95_left_anterior` | `I267_1` | Hz | SEF 95 Left Ant, Left Anterior | FFT_Edge 95 0-32 Left Anterior_avg | P-DOC |
| `sef_95_left_hemisphere` | `I276_1` | Hz | SEF95, Left Hemisphere | FFT_Edge 95 0-32 Left Hemisphere_avg | P-DOC |
| `sef_95_left_posterior` | `I268_1` | Hz | SEF 95 Left Post, Left Posterior | FFT_Edge 95 0-32 Left Posterior_avg | P-DOC |
| `sef_95_posterior` | `I277_1` | Hz | SEF95, Posterior | FFT_Edge 95 0-32 Posterior_avg | P-DOC |
| `sef_95_right_anterior` | `I269_1` | Hz | SEF 95 Right Ant, Right Anterior | FFT_Edge 95 0-32 Right Anterior_avg | P-DOC |
| `sef_95_right_hemisphere` | `I278_1` | Hz | SEF95, Right Hemisphere | FFT_Edge 95 0-32 Right Hemisphere_avg | P-DOC |
| `sef_95_right_posterior` | `I270_1` | Hz | SEF 95 Right Post, Right Posterior | FFT_Edge 95 0-32 Right Posterior_avg | P-DOC |

### spike_density

**Units:** spikes/sec

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `spike_all_foci_per_sec` | `I301_1` | spikes/sec | Spike Detections, all foci (count per sec) | SpikeDensityV1 | P-DOC |
| `spike_bilateral_indicator_per_10s` | `I305_1` | spikes/sec | Spikes >=3 per ten seconds L&R (blue=left, red=right, yellow=L&R) | [>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike… | P-DOC |
| `spike_burst` | `I293_1` | spikes/sec | Spike Burst Detections | EventDensity SpikeBurst <Detector,Count_overlap> | P-DOC |
| `spike_generalized_indicator_per_10s` | `I308_1` | spikes/sec | Spikes >=3 per ten seconds generalized (blue=left, red=right, yello… | [>= 3 <0> [EventDensity SpikeGen <Detector,Count_epoch>01]] AND [>=… | P-DOC |
| `spike_generalized_per_10s` | `I294_1` | spikes/sec | Spike Detections generalized (count per 10s) | EventDensity SpikeGen <Detector,Count_epoch> | P-DOC |
| `spike_generalized_per_sec` | `I295_1` | spikes/sec | Spike Detections generalized (count per sec) | EventDensity SpikeGen <Detector,Count_epoch>01 | P-DOC |
| `spike_generalized_threshold_per_sec` | `I303_1` | spikes/sec | Spike RateThreshold, generalized >=3 per 10 sec, Spike Detections g… | >= 3 <0> [EventDensity SpikeGen <Detector,Count_epoch>01] | P-DOC |
| `spike_left_indicator_per_10s` | `I307_1` | spikes/sec | Spikes >=3 per ten seconds left (blue=left, red=right, yellow=L&R, … | [>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike… | P-DOC |
| `spike_left_per_10s` | `I296_1` | spikes/sec | Spike Detections left hemisphere (count per 10 sec) | EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike C3 OR Spik… | P-DOC |
| `spike_left_per_sec` | `I297_1` | spikes/sec | Spike Detections left hemisphere (count per sec) | EventDensity Spike Fp1 OR Spike FP1 OR Spike F3 OR Spike C3 OR Spik… | P-DOC |
| `spike_left_threshold_per_10s` | `I304_1` | spikes/sec | Spike RateThreshold, left hemisphere >=3 per 10 sec, Spike Detectio… | >= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike FP1 OR Spike … | P-DOC |
| `spike_right_indicator_per_10s` | `I306_1` | spikes/sec | Spikes >=3 per ten seconds right (blue=left, red=right, yellow=L&R) | [>= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike… | P-DOC |
| `spike_right_per_10s` | `I298_1` | spikes/sec | Spike Detections right hemisphere (count per 10 sec) | EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike C4 OR Spik… | P-DOC |
| `spike_right_per_sec` | `I299_1` | spikes/sec | Spike Detections right hemisphere (count per sec) | EventDensity Spike Fp2 OR Spike FP2 OR Spike F4 OR Spike C4 OR Spik… | P-DOC |
| `spike_right_threshold_per_10s` | `I302_1` | spikes/sec | Spike Rate Threshold, right hemisphere >=3 per 10 sec, Spike Detect… | >= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike FP2 OR Spike … | P-DOC |
| `spike_vertex_per_sec` | `I300_1` | spikes/sec | Spike Detections vertex (count per sec) | EventDensity Spike Fz OR Spike FZ OR Spike Cz OR Spike CZ OR Spike … | P-DOC |

### status_epilepticus

**Units:** binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.050331, never 0; advanced and combined are identical — see docs/DATA_DICTIONARY_v4.md

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `status_epilepticus_persyst_acns_binary` | `I309_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus ACNS Metric (Binary) | Electrographic Status Epilepticus | MMX |
| `status_epilepticus_persyst_acns_percent` | `I310_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus ACNS Metric (Percent) | Electrographic Status Epilepticus01 | MMX |
| `status_epilepticus_persyst_advanced_binary` | `I311_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Advanced Metric (Binary) | Electrographic Status Epilepticus02 | MMX |
| `status_epilepticus_persyst_advanced_percent` | `I312_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Advanced Metric (Percent) | Electrographic Status Epilepticus03 | MMX |
| `status_epilepticus_persyst_combined_binary` | `I313_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Combined Metric (Binary) | Electrographic Status Epilepticus04 | MMX |
| `status_epilepticus_persyst_combined_percent` | `I314_1` | binary (0/1) or % (0–100) per variant. PERCENT variants floor at 0.… | Status Epilepticus Combined Metric (Percent) | Electrographic Status Epilepticus05 | MMX |

### suppression_ratio

**Units:** % (0–100)

| Column | I-code | Units | CSV header | MMX instrument | Tier |
|---|---|---|---|---|---|
| `suppression_all` | `I323_1` | % (0–100) | Suppression Ratio, All 10-20 | BSR All 10-20_avg | P-DOC |
| `suppression_anterior` | `I324_1` | % (0–100) | Suppression Ratio, Anterior | BSR Anterior_avg | P-DOC |
| `suppression_left` | `I326_1` | % (0–100) | Suppression Ratio, Left Hemisphere | BSR Left Hemisphere_avg | P-DOC |
| `suppression_left_anterior` | `I325_1` | % (0–100) | Suppression Ratio, Left Anterior | BSR Left Anterior_avg | P-DOC |
| `suppression_left_posterior` | `I327_1` | % (0–100) | Suppression Ratio, Left Posterior | BSR Left Posterior_avg | P-DOC |
| `suppression_posterior` | `I328_1` | % (0–100) | Suppression Ratio, Posterior | BSR Posterior_avg | P-DOC |
| `suppression_right` | `I330_1` | % (0–100) | Suppression Ratio, Right Hemisphere | BSR Right Hemisphere_avg | P-DOC |
| `suppression_right_anterior` | `I329_1` | % (0–100) | Suppression Ratio, Right Anterior | BSR Right Anterior_avg | P-DOC |
| `suppression_right_posterior` | `I331_1` | % (0–100) | Suppression Ratio, Right Posterior | BSR Right Posterior_avg | P-DOC |

---

*Generated by `scripts/gen_column_map_md.py` from the CSV. Regenerate both with `gen_column_map_v10.py` first.*
