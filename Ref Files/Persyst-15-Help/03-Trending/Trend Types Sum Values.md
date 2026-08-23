---
title: "Trend Types: Sum Values"
source: persyst-15-help
section: "Trending"
htmFile: "Trend_Types__Sum_Values.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Sum Values

# Trend Types: Sum Values

A Sum Values trend evaluates data from a user-specified trend and plots the sum of the values as a function of time using the specified method (e.g., Sum Values, Avg Values, or Percentile). This can be used to sum the values in a 3-D trend to express them as a line trend.

Method: The user specifies an existing trends, the method of summing the values, and an optional title for the trend. For each time epoch, the Sum Values operation provides a sum, an average, or the value below the specified percentile. For spectrogram 3-D trends, the Lower Index and Upper Index is set "-1 to -1" for all values in the spectrogram. The output is plotted as a line graph.

- User-adjustable parameters:
- - For Sum Values trend calculations: the trend on which the Sum Values operation will be performed, and the Function (Sum Values, Avg Values, or Percentile.
  - For Sum Values trend graph: x-axis duration (timescale), y-axis range, color and optional fill color used for line graph, graph title.
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: an example Sum Values trend is not included in the example file.