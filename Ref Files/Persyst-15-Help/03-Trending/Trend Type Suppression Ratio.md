---
title: "Trend Type: Suppression Ratio"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Type_Suppression_Ratio.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Type: Suppression Ratio

# **Trend** **Type: Suppression Ratio**

The Suppression Ratio trend displays a running average of the percentage of EEG activity that falls below a user specified amplitude threshold, as a function of time. Time is displayed on the x-axis and the Suppression Ratio measure (%) on the y-axis. The Suppression Ratio trend is intended to be used in conjunction with other EEG trends, and with the original EEG waveforms, for analysis of the EEG.

Method:
This graphical depiction of EEG
trend
data displays values derived by assessing the amplitude of the existing EEG waveform (as recorded by OEM EEG equipment). For a user-specified epoch duration and sampling rate, the duration (seconds) of individual EEG s
egments in the epoch that meet the following criteria is calculated: all absolute amplitude values in the segment fall below a user-specified amplitude threshold, and the low-amplitude segment duration exceeds a user-specified minimal duration threshold.
T
he durations of all such segments in an epoch are then summated, and the result is divided by the epoch duration and multiplied by 100 to yield the suppression percentage for the epoch. The resulting value is averaged via a user-specified time window to y
i
eld the Suppression Ratio measurement. The Suppression Ratio is plotted as a line graph.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the
      Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the
      Suppression
      Ratio analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition e
      quipment. Groups of channels can also be specified so that Suppression Ratio trend graphs representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or t
      h
      e anterior left hemisphere), can be displayed.
  - For Suppression Ratio trend calculations: sampling rate (Hz), epoch duration (seconds), “flat” duration threshold (seconds), “flat” amplitude threshold (µV).
  - For Suppression Ratio trend graph: duration (second
    s) of time window used for averaging, x-axis duration (timescale), y-axis range (%), and color and optional fill color used for line graph
    .
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: Epoch duration: 10 seconds, Sampling Rate: 128 Hz, Flat Duration Threshold: 0.5 seconds, Flat Duration Amplitude: 3 µV, Running Average duration: 60 seconds. Example Suppression Ratio trends display averages of Suppression Ratio data from the left hemisphere
  (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1) and right hemisphere (Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2).