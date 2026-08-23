---
title: "Trend Types: Rhythmicity"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Rhythmicity.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Rhythmicity

# **Trend** **Types: Rhythmicity**

**Rhythmicity Spectrogram**
:
The Rhythmicity Spectrogram trend displays a
density spectral array of frequency and power characteristics of the EEG as a function of time. Time is displayed on the x-axis, frequency on the y-axis, and a measure of EEG power on the z-axis as a color scale. The Rhythmicity Spectrogram provides a gra
p
hical depiction of the amplitude of primary rhythmic EEG components present in four frequency bands spanning 1-25 Hz. The Rhythmicity function is intended to be used in conjunction with the original EEG waveforms, and with other EEG trends, for analysis o
f
the EEG.

Method: This graphical depiction of EEG
trend
data displays values derived from the frequency and power outputs of analysis performed on the EEG signal. The Rhythmicity Spectrogram data derive from calculations performed as an intermediate step
of the Persyst Seizure Detector algorithm. Because multiple rhythmic frequencies are often present in the EEG,
the rhythmicity is calculated in
four bands: 1-4 Hz, 4-9 Hz, 9-16 Hz and 16-25 Hz.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the Rhythmicity
      calculation
      analysis will be performed: the EE
      G montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that Rhythmicity spectrograms representing statistical aggregations of channel data, such
      a
      s the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For Rhythmicity calculation: analysis epoch duration (seconds), analysis duration step size (seconds).
  - F
    or Rhythmicity Spectrogram graph: x-axis duration (timescale), y-axis frequency range (Hz), y-axis scale type: linear or square root scaled (for better low frequency visualization on graph), z-axis power scale type (depending on user analysis needs, power
    parameter expressed as µV², µV, dB, or sqrt(µV)), z-axis (power scale) range, and color palette used for z-axis (power) data
    .
- Parameter settings utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: EEG time constant
  = 0.16 seconds, high-frequency filter = 35 Hz, Rhythmicity sampling rate = 128 Hz, epoch duration = 3 seconds, epoch step = 2 seconds, y-axis range 1-25 Hz, y-axis scaling type = square root, z-axis scaling using µV/Hz, z-axis range 0-4 µV/Hz, z-axis colo
  r
  palette: YellowGreenBlue9CB. Example trends display averages of Rhythmicity Spectrogram data from the left hemisphere (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1) and right hemisphere (Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O
  2
  ), and also multiple channels individually (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1, Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2, Fz-Cz, Cz-Pz).