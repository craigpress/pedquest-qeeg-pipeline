---
title: "Trend Types: Amplitude"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Amplitude.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Amplitude

# **Trend** **Types: Amplitude**

The Amplitude trend displays amplitude, signal slope, zero-crossing frequency, or statistical information concerning amplitude, of the EEG signal as a function of time. Time is displayed on the x-axis and the Amplitude measure on the y-axis. The Amplitude trend is intended to be used in conjunction with other EEG trends, and with the original EEG waveforms, for analysis of the EEG.

Method: This graphical depiction of EEG
trend
data displays values derived by assessing the amplitude, amplitude versus time, or zero-crossing properties of the existing
EEG waveform (as recorded by OEM EEG equipment). For a user-specified epoch duration, any of the following EEG parameters can be graphically displayed:

- Max: Maximum absolute amplitude in epoch (based on absolute value of baseline-to-peak amplitude)
- Avg: A
  verage amplitude in epoch (based on absolute value of baseline-to-peak amplitude)
- StdDev: Standard deviation of amplitude in epoch (based on absolute value of baseline-to-peak amplitude)
- DCAvg: Average DC Amplitude in epoch (based on signed value of baseli
  ne-to-peak amplitude)
- FlatDurMax: Duration (seconds) of longest EEG segment in an epoch in which all absolute amplitude values fall below a user-specified threshold and the segment duration exceeds a user-specified minimal duration threshold
- FlatDurSum: Su
  mmated duration (seconds) of all EEG segments in an epoch in which all absolute amplitude values fall below a user-specified threshold and the individual segment duration exceeds a user-specified minimal duration threshold
- ZCFreqAve: Average zero (baseline
  ) crossing frequency in epoch
- ZCFreqStdDev: Standard deviation of the zero (baseline) crossing frequency
- ZCAmpAvg: Average signal maxima amplitude, calculated as the mean per epoch of the absolute values of signal maxima between each zero crossing
- ZCAmpStd
  Dev: Standard deviation of signal maxima amplitude, calculated per epoch as the standard deviation of the absolute values of signal maxima between each zero crossing
- SlpAvg: mean of the absolute values of signal slopes for the epoch (signal slope calculate
  d as the absolute value of the amplitude difference between a signal sample point and the previous sample point, multiplied by the sampling rate)
- SlpMax: maximum value of the absolute values of signal slopes for the epoch (signal slope calculated as the ab
  solute value of the amplitude difference between a signal sample point and the previous sample point, multiplied by the sampling rate)
- ZCSlpAvg: mean of the signal slope values at zero-crossing points
- ZCSlpMax: maximum value of signal slope at zero-crossin
  g points in the current epoch
- ZCSlpAsymmetry: asymmetry of slopes crossing zero to positive values and zero to negative values; calculated as ((abs(A)/(abs)B)-1)\*ZCSlpAvg, where A and B are average slopes for two directions, arranged so that A>B

The re
sult is plotted as a line graph.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis mont
      age specifying channels on which the Amplitude analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that Ampl
      i
      tude trend graphs representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For Amplitude trend calcu
    lations: sampling rate (Hz), epoch duration (seconds), “flat” duration threshold (seconds), “flat” amplitude threshold (µV).
  - For Amplitude trend graph: Amplitude parameter to be displayed (see list above), x-axis duration (timescale), y-axis amplitude rang
    e (µV, Hz, or µV/sec depending on user selection of parameter to be displayed), and color and optional fill color used for line graph
    .
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: an example Amplitude trend is not included in the example file.