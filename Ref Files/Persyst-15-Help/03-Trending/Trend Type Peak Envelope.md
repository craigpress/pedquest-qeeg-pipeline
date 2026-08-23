---
title: "Trend Type: Peak Envelope"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Type_Peak_Envelope.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Type: Peak Envelope

# **Trend** **Type: Peak Envelope**

The Peak Envelope tren
d displays a time-smoothed representation of a band-pass-filtered EEG's maximal amplitude envelope as a function of time. Time is displayed on the x-axis and the Peak Envelope amplitude measure on the y-axis. The Peak Envelope trend provides a simplified
d
epiction of amplitude characteristics of the EEG signal, and is intended to be used in conjunction with other EEG trends, and with the original EEG waveforms, for analysis of the EEG.

Method: This graphical depiction of EEG
trend
data displays values der
ived via the following method. The existing EEG waveform (as recorded by OEM EEG equipment) is first filtered by a user-selectable band-pass filter. Then, the maximum (i.e., peak) absolute value (µV) in each one-second epoch of the resulting signal is det
e
rmined. Finally, a running average of these values is calculated over a user-specified moving time window. The result is graphed as a line graph.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - EEG analysis montage specifying channels on w
      hich the Peak Envelope analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that Peak Envelope graphs represe
      n
      ting statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For Peak Envelope calculation: sampling rate (Hz);
    minimum and maximum values for band-pass filter (Hz).
  - For Peak Envelope graph: time window duration for running average, x-axis duration (timescale), y-axis amplitude range (µV), and color and optional fill color used for line graph
    .
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: Peak Envelope sampling rate = 128 Hz, Peak Envelope band-pass settings: 2-20 Hz, time window duration for running average: 10 seconds, y-axis range 0-100 µV, line graph colors red and blue. Example trends display averages of Peak Envelope data from the left hemisphere (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1) and right hemisphere (Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2).