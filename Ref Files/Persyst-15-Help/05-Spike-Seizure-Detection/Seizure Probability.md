---
title: "Seizure Probability"
source: persyst-15-help
section: "Spike and Seizure Detection"
htmFile: "Seizure_Probability.htm"
tags:
  - persyst
  - persyst-help
  - spike-seizure-detection
---

# Seizure Probability

# **Seizure Probability**

Persyst 14
Trending
includes both seizure detection and seizure probability
trends.
These
are closely related and represent stages in the output of the
Persyst seizure detector algorithm. The seizure detector algorithm works
by taking numerous inputs and combining them into a probability value.
This
probability value is one of 0.0, 0.2, 0.4, 0.6, 0,8 or 1.0. The
seizure probability represents the probability
that the epoch represents an electrographic seizure. Thus, for example,
if an epoch were given a value of 0.2 we would expect that there is a
20 percent chance that this epoch represents an electrographic seizure

The Seizure Probability
trend
provides
a display of the
calculated
seizure probability. This contrasts
with the Seizure Detection
trend
that
provides a discrete value of zero or one depending on whether a seizure
has been detected. Thus the
Seizure
Probability
trend
provides
more detail about the results of the Persyst seizure detection algorithm
than the Seizure Detection
trend.
This detailed seizure probability
information may be relevant to users who would like
to see cases where there is some indication of seizure activity that does
not rise to a sufficient level to be considered a seizure detection. It
may also be useful to understand the level of certainty in cases where
there is a seizure detection

The Seizure
Probability trend uses a bar graph to show the Persyst Seizure detector
output scaled so that the height of the bar represents the probability
that the interval represents an electrographic seizure. Since the Seizure
Detection
Probability function is validated at discrete values of 0.0, 0.2, 0.4,
0.6, 0.8 and 1.0 only those discrete values are presented.

User-adjustable
parameters:

1. o   For
   EEG signal to be analyzed: none

   o Probability
   (Detect): Sets the minimum Perception value (maximum sensitivity)
   for seizure detections. The default value is 0.5.

   o Probability
   (Early Detection): Sets the minimum Perception value (minimum sensitivity)
   for seizure detections that will be displayed in the Comment List
   and on the Seizure Detection trend. The default value is 0.8.

   o Duration
   (Detect): Sets the minimum Duration value in seconds for seizure detections.
   The default value is 8 seconds.

   o Duration
   (Early Detection): Sets the minimum Duration value in seconds for
   seizure detections that will be displayed in the Comment List and
   on the Seizure Detection trend. The default value is 8 seconds.   

   o   For
   Seizure Detection graph: x-axis duration (timescale), y-axis range,
   and color for bar graph and optional color fill.

   o   Parameter
   settings utilized in default trends shipped with software: y-axis
   range 0 – 1.0, graph line color: none, graph fill color: red.Trend
   Output: Probability (0-1), Detections (probability and duration exceeded),
   or Notifications (seizure notification generated).

   o   Acquisition
   Latency Thresholds Stop|Restart Processing: When data is interrupted/paused
   during on-line processing, automatically pause and restart seizure
   detection (seconds). Default Stop: 120s. Default Restart: 60s.

   o   Montage:
   Not user adjustable.

The channel montage
used by the Persyst Seizure Detector is fixed and cannot be changed by
the user.