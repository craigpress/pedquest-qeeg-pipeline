---
title: "Trend Types: Frequency"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Frequency.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Frequency

# **Trend** **Types: Frequency**

**FFT Spectrogram**
:
The FFT Spectrogram trend displays a density spectral array of the frequency and power characteristics of the EEG, derived from a fast Fourier transform analysis, as a funct
ion of time. Time is displayed on the x-axis, frequency on the y-axis, and a measure of EEG power on the z-axis as a color scale.

Method: This grap
hical depiction of
EEG
trend
data displays values derived from the frequency and power outputs of a fast Four
ier transform analysis performed on the EEG signal.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the FFT analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified s
      o that FFT spectrograms representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For FFT: sampling r
    ate, points per window, window duration, windows per epoch, overlapped windows, and smoothing.
  - For FFT Spectrogram graph: x-axis duration (timescale), y-axis frequency range (Hz), z-axis power scale type (depending on user analysis needs, power parameter e
    xpressed as µV², µV, dB, or sqrt(µV)), z-axis (power scale) range, and color palette used for z-axis (power) data
- Parameter settings utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: time constant = 0.16 seconds,
  high-frequency filter = 35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows per epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range 0-20 Hz, z-axis scaling using sqrt(µV)/Hz, z-axis r
  a
  nge 0-2 sqrt(µV)/Hz, z-axis color palette RGBCube. Example trends display averages of FFT Spectrogram data from the left hemisphere (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1) and right hemisphere (Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4,
  C4-P4, P4-O2).

**FFT****Power**
:
The FFT Power trend displays a line graph of power in a user-specified frequency band of the EEG, derived from a fast Fourier transform analysis, as a function of time. Time is displayed on the x-axis and a
measure of EEG power on the y-axis.

Method: This graphical depiction of EEG
trend
data displays values derived from the frequency and power outputs of a fast Fourier transform analysis performed on the EEG signal. The user specifies the frequency band and
power scale to be used in the power calculation.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - E
      EG analysis montage specifying channels on which the FFT Power analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specif
      i
      ed so that FFT Power graphs representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For FFT: sampli
    ng rate, points per window, window duration, windows per epoch, overlapped windows, and smoothing.
  - For FFT Power graph: frequency limits for power value to be displayed (e.g., 4-8 Hz), x-axis duration (timescale), y-axis frequency range (power), y-axis pow
    er parameter utilized for graphing (depending on user analysis needs, power parameter can be expressed as µV², µV, dB, or sqrt(µV), all derived from the FFT power output data), and color (and optionally, fill color) used for line graph
- Parameter settings
  utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: time constant = 0.16 seconds, high-frequency filter = 35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows pe
  r epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range variable depending on graph, y-axis scaling using µV, line graph color variable depending on graph. FFT Power graph examples showing power in the following frequency ranges are included
  :
  1-4 Hz, 4-8 Hz, 8-13 Hz, 13-20 Hz. These data are displayed for the left and right hemispheres as a two minute running time average (left hemisphere: Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1; right hemisphere: Fp2-F8, F8-T4, T4-T6, T6-O2,
  Fp2-F4, F4-C4, C4-P4, P4-O2).

**FFTPower Ratio**
:
The FFT PowerRatio trend displays a line graph of a ratio of power in two user-specified frequency bands of the EEG, derived from a fast Fourier transform analysis, as a function of time
. Time is displayed on the x-axis and the power ratio result on the y-axis.

Method: This graphical depiction of EEG
trend
data displays values derived from the frequency and power outputs of a fast Fourier transform analysis performed on the EEG signal. T
he user specifies the power scale and frequency bands to be used in the numerator and denominator of the power ratio calculation (e.g., 8-13 Hz/1-4 Hz).

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant,
      high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the FFT PowerRatio analysis will be performed: the EEG montages that can be specified are limited to the
      original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that FFT PowerRatio graphs representing statistical aggregations of channel data, such as the average of values from several channels (e.g.,
      a
      grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For FFT: sampling rate, points per window, window duration, windows per epoch, overlapped windows, and smoothing.
  - For FFT PowerRatio graph: frequency limits f
    or power values to be utilized as numerator and denominator values (e.g., 8-13 Hz/1-4 Hz), power scale type to be used in power ratio calculation (depending on user analysis needs, power parameter can be expressed as µV², µV, dB, or sqrt(µV)), x-axis dura
    t
    ion (timescale), y-axis range, and color (and optionally, fill color) used for line graph
    .
- Parameter settings utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: time constant = 0.16 seconds, high-frequency filter =
  35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows per epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range variable depending on graph, power scale expressed as µV/Hz, y-axis range 0
  .1-2.0, line graph color variable depending on graph left-sided electrodes in blue and right-sided in red). FFT PowerRatio graph examples showing power ratios for the following frequency ranges are included: (8-13 Hz)/(1-4 Hz). These data are displayed fo
  r
  the left and right hemispheres, left and right anterior, and left and right posterior as a two minute running time average (left hemisphere: Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1; right hemisphere: Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4,
  F
  4-C4, C4-P4, P4-O2; left anterior Fp1-F7, F7-T3, Fp1-F3, F3-C3; right anterior: Fp2-F8, F8-T4, Fp2-F4, F4-C4; left posterior: T3-T5, T5-O1, C3-P3, P3-O1; right posterior: T4-T6, T6-O2, C4-P4, P4-O2).

**FFT Edge**
:
The FFT Spectral Edge t
rend displays a line graph, as a function of time, of the frequency below which a designated percentage of a user-specified EEG frequency band
’
s total power is present. Time is displayed on the x-axis and the spectral edge frequency (Hz) on the y-axis. Fo
r
example, for the frequency band 0-20 Hz and Edge percentage setting of 95, a resulting Spectral Edge value of 14 Hz means that 95% of the EEG
’
s power in the 0-20 Hz range occurs below a frequency of 14 Hz.

Method: This graphical depiction of EEG
trend
da
ta displays values derived from the frequency and power outputs of a fast Fourier transform analysis performed on the EEG signal. The user specifies the frequency band (minimum and maximum frequencies), spectral edge percentage, and power scale to be
used
in the power calculation.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage spec
      ifying channels on which the FFT analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that FFT Spectral Edge
      t
      rends representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For FFT: sampling rate, points per wi
    ndow, window duration, windows per epoch, overlapped windows, and smoothing.
  - For FFT Spectral Edge graph: frequency limits for spectral edge calculation (e.g., 0-32 Hz), x-axis duration (timescale), y-axis frequency range (Hz), power scale utilized for spe
    ctral edge calculation (depending on user analysis needs, power parameter can be expressed as µV², µV, dB, or sqrt(µV), all derived from the FFT power output data), and color (and optionally, fill color) used for line graph.
- Parameter settings utilized i
  n default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: an example FFT Spectral Edge trend is not included in the example file.