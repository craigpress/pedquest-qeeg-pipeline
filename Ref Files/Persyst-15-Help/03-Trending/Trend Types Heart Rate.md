---
title: "Trend Types: Heart Rate"
source: persyst-15-help
section: "Trending"
htmFile: "Trend_Types_Heart_Rate.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Heart Rate

# **Trend Types: Heart Rate**

The Heart Rate trend measurement is based on the ECG channel in the EEG recording. The ECG analysis is not sufficient by itself to mark an event. The ECG channel is configured according to the ECG channels / labels configured on the EEG acquisition system to enable ECG analysis during on-line or off-line processing of trends and event detection.

The absence of an ECG channel or failure to set up the channel for analysis does not impede or have any effect on the function of the other detectors.

(Refer to Appendix A for information on the performance characteristics of Persyst Heart Rate measurement.)

Method: Persyst Heart Rate Measurement Algorithm.

User-adjustable parameters:

- - For ECG signal to be analyzed: G1 and G2 (channel 1 and channel 2).
  - For number of beats to average: Sets the number of beats used to calculate the heart rate. The default value is 15.
  - For Epoch Duration (sec): Sets the epoch length for the x-axis duration (update). The default value is 1.
  - For Heart Rate graph: x-axis duration (timescale), y-axis range, and color for line graph and optional color fill.

See the help topic 
Trend Preferences: EKG Channels

 for information on configuring the Heart Rate trend channels.