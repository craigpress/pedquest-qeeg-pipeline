---
title: "Trend Types: Weighted Sum"
source: persyst-15-help
section: "Trending"
htmFile: "Trend_Types_Weighted_Sum.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Weighted Sum

# **Trend Types: Weighted Sum**

A Weighted
Sum trend evaluates data from a user-specified weighted list of existing two-dimensional trends, and plots the sum of the weighted valu
es as a function of time.

Method: The user specifies a list of existing trends, an individual weighting value for each trend in the list, and an optional title for the trend. For each time epoch, the WeightedSum operation multiplies each individual trend
’
s value by its weighting factor, then summates the results from the list (e.g., if there are three designated trends
–
Trend1, Trend2, and Trend3
—
with respective values at time t1
of 10, 5, and 8, and respective weights 1.0, 1.0, and 2.0, then the output o
f the WeightedSum trend at time t1
is 31 (10\*1 + 5\*1 + 8\*2). Optionally, an Offset value can be assigned which will offset (shift) the result by the specified value (e.g., if an Offset of 10 were specified for the prior example, the final result would be 3
1 + 10 = 41). The output is plotted as a line graph.

- User-adjustable parameters:
- - For WeightedSum trend calculations: a list of two-dimensional trends (line graphs) on which the WeightedSum operation will be performed, a weighting value for each trend o
    n that list, and, optionally, an Offset value to be added to the initial calculation result
  - For WeightedSum trend graph: x-axis duration (timescale), y-axis range, color and optional fill color used for line graph, graph title.
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: an example WeightedSum trend is not included in the example file.