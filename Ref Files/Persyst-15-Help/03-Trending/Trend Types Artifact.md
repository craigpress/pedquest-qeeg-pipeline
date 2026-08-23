---
title: "Trend Types: Artifact"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Artifact_Intensity.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Artifact

# **Trend** **Types: Artifact**

**Artifact Intensity**
:
The Artifact Intensity trend displays color-scaled indicators representing the presence of
three
physiological non-cere
bral signals (muscle
, vertical saccadic ey
e movement/blink, and horizontal saccadic eye movement) in the EEG as a function of time. The values graphed in this trend are outputs of intermediate steps in the
Seizure Detection and
Artifact Reduction algorithm
s
, and are intended to be used in conjunct
ion with the original
EEG waveforms, and with other
EEG trends, for analysis of the EEG.

Method: This graphical depiction of output from intermediate steps in the Artifact Reduction algorithm (see sections concerning Artifact Reduction algorithm) plots va
lues concerning the quantity of vertical eye movement and blink detections, lateral saccadic eye movement detections,
and
muscle activity, as color-scaled horizontal bar graphs on the y-axis versus time on the x-axis. The values for eye movement quantity d
erive from the output of neural networks designed to detect saccadic vertical eye/blink and lateral eye movement artifacts.
The muscle artifact intensity trend reflects the maximum amount of muscle artifact removed from any of the channels in the recorded
montage. For each channel in the recorded montage the average power (uV2
) of the muscle activity removed by the Artifact Reduction (AR) algorithm during each ten-second epoch is calculated. The value of the trend is equal to the maximum value of the calcul
ation across all channels. The scale is user-adjustable and by default the maximum color is reached when the average power during the epoch is 100
.
These data are summarized for 10-second epochs and plotted on an adjustable color scale that is individually
set for each artifact type. The artifact type (Muscle, V-Eye, L-Eye) is labeled in a color-coded legend along the right y-axis of the trend graph.

- User-adjustable parameters:
- - For EEG signal to be analyzed: none
  - For Artifact Intensity calculations: none
  - For Artifact Intensity graph: x-axis duration (timescale), color for color scale and labels of individual artifact types, Number of color levels for color scales, Line thickness for artifact horizontal line plots, maximum range for color scale for each ar
    tifact type
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: Muscle artifact color scale: white-to-green, Muscle artifact color scale max value 100, V-Eye color scale: white-to-blue, V-Eye artifact color scale max value 1.0, L-Eye color scale: white-to-brown, L-Eye artifact color scale max value 1.0, Line thickness: 3, Number of Levels: 100
- Persyst validation testing yielded the following results.
- - Vertical Eye: Sensitivity 93.2 %,  Specificity 9
    9 %
  - Lateral Eye: Sensitivity 87.5 %,  Specificity 97.3%

**Electrode Signal Quality**
:
The
Electrode Signal Quality trend displays horizontal bar indicators representing the presence of possible electrode artifact in the montag
e being used for EEG
trend
measures as a function of time. The values graphed in this trend are outputs of intermediate steps in the Artifact Reduction algorithm, and are intended to be used in conjunction with the original EEG waveforms, and with other EE
G trends, for analysis of the EEG.

Method: This graphical depiction of output from intermediate steps in the Artifact Reduction algorithm plots values concerning the
amount
of electrode artifact in individual channels of the montage being used for EEG
tre
nd
measure calculations, as horizontal bar graphs on the y-axis versus time on the x-axis. The values for electrode artifact derive from the output of Artifact Reduction algorithm neural networks designed to assess the
amount
of electrode artifact being pr
esent at any one-second instant in time. These data are plotted using an adjustable color scale. The channels utilized in the montage being used for EEG
trend
measure calculations are labeled along the y-axis.

- User-adjustable parameters:
- - For EEG signal
    to be analyzed: none
  - For electrode artifact calculations: none
  - For Electrode Signal Quality graph: x-axis duration (timescale), color for color scale, minimum and maximum range for color scale
    .
- Parameter settings utilized in default trend examples (
  Trend
  Settings Version P15.mmx
  ) shipped with software: An example Electrode Signal Quality trend is not included with the example file.
- Click 
  HERE
  for
  information on the performance char
  acteristics of Persyst Electrode Artifact Detection.