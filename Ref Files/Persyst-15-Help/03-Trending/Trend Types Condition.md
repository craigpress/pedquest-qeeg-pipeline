---
title: "Trend Types: Condition"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Condition.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Condition

# **Trend** **Types: Condition**

Condition
trends
take on only two values, 0 (false) and 1 (true).

**Threshold****:**
A Threshold trend evaluates data from an existing trend against a user-specified threshold criterion, and returns a value of 0 or 1, as a function of time, depending on whether the criterion is met.

Method: The user specifies a Trend for threshold evaluation; Threshold Attributes consisting of an Operator (>, >=,+,<,<=), Cutoff value, and Duration (seconds); and optionally a name for the threshold Trend Title. The Threshold operation returns a value of 0 (false) if the conditions are not met, and 1 (true) if the conditions are met. The output is plotted as a line graph with epoch duration equal to the epoch duration of the trend being evaluated.

- User-adjustable parameters:
- - For Threshold trend calculation: Trend to be evaluated, Threshold Attributes consisting of an Operator (>, >=,+,<,<=), Cutoff value, and Duration (seconds).
  - For Threshold trend graph: x-axis duration (timescale), y-axis range, color and optional fill color used for line graph, graph title.
- Parameter settings utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: an example Threshold trend is not included in the example file.

**Boolea****n:**
A Boolean trend evaluates data from two existing conditional trends (i.e., those trends whose values are exclusively 0 (false) or 1 (true), like Threshold trends) using Boolean operators (AND, OR, XOR, and optional NOT) and return values of 0 (false) or 1 (true) as a function of time.

Method: The user specifies two conditional trends and the Boolean operator (AND, OR, XOR, and optional NOT) for the calculation. The output is plotted as a line graph. The epoch duration for the resulting Boolean trend equals the shorter of the two epoch durations present in the originally evaluated conditional trends.

# Condition Statistics: Event density trends can be used to counting events and their durations; however, for threshold or Boolean events (e.g., outputs of 1)., the use of the Condition Statistics trend may be better suited where the ability to modify the input parameters dynamically is required.

Count\_epoch    Count1

Count\_sec    Count1/sec

Count\_min    Count1/min

Count\_hour    Count1/hr

Duration\_sum    Dur1

Duration\_sec    Dur1/sec

Duration\_min    Dur1/min

Duration\_hour    Dur1/hour

Duration\_avg    Dur1/Count1

Whereas: Count1 - count of source transitions 0->1. This assumes that initial value is 0, so if the source=1 whole epoch, Count1=1 (equivalent to Count\_epoch of EventDensity);

Dur1 - total duration of segments within the epoch where source=1 (equivalent of Duration\_sum of EventDensity)