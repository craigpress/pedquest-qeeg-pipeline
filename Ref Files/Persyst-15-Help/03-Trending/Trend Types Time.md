---
title: "Trend Types: Time"
source: persyst-15-help
section: "Trending"
htmFile: "Trend_Types_Time.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Time

# **Trend Types: Time**

**Time:**
A Time trend performs an operation on multiple epochs of an existing
two-dimensional trend, and plots the result as a function of time. Available operations include calculation of the mean, minimum, maximum, standard deviation, or a ranked percentage (e.g., 25th
percentile or 75th
percentile) across the specified epoch ran
ge.

Method: The user specifies an operation to be performed (mean, minimum, maximum, standard deviation, or a ranked percentage) and the duration, in seconds, of the multi-epoch range to which the chosen operation will apply. Optionally, a lag can be spec
ified if the operation for the current epoch is to return the value for a range of epochs that precedes the current epoch.

- User-adjustable parameters:
- - For Time trend calculations: Trend on which the Time Trend operation will be performed, Duration of m
    ulti-epoch range on which operation will be performed, Operator (avg, min, max, StdDev, percentile), Lag (seconds)
  - For Time trend graph: x-axis duration (timescale), y-axis range, and color and optional fill color used for line graph
- Parameter settings u
  tilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: Time trend graphs depicting
  two-
  minute time-averaged values of FFT PowerRatio trends are shown. These data are displayed for the left and right hemispheres, left and
  right anterior, and left and right posterior as a two minute running time average (left hemisphere: Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1; right hemisphere: Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2; left anterior Fp1-F7,
  F7-T3, Fp1-F3, F3-C3; right anterior: Fp2-F8, F8-T4, Fp2-F4, F4-C4; left posterior: T3-T5, T5-O1, C3-P3, P3-O1; right posterior: T4-T6, T6-O2, C4-P4, P4-O2).