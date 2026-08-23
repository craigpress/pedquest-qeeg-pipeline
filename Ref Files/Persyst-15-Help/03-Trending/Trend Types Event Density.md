---
title: "Trend Types: Event Density"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Other.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Event Density

## **Trend** **Types:** **Event Density**

**Event** **Density**
:
An EventDensity trend generates a graphical depiction of information contained in user-designated comments from the comments or comment file that accompanies an EEG recording. Either the presence or presence and duration of a user-
specified comment can be graphed against time, or the presence of a specified comment and numeric data associated with that comment can be graphed against time.

Method: First, an Epoch Duration (seconds) is assigned for graphing specified comments. Next t
he user specifies the Event Text to be used as the basis for the graphical representation of comments containing matching text. Optionally, a specific source from which that text was derived (Any Origin, Insight, Recorded text, Recording change, or Detect
o
r) can be designated. The method by which the comment will be graphically represented (Sum Type) is then specified, per the following choices (note: to use the Perception\_... functions a designated comment “xyz” must follow the format “xyz p=x”, where p r
e
presents the perception variable and x is the perception value number attached to that comment):

- Count\_epoch: yields a graph of a count of the designated comments per user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set
  to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-second epoch, then the EventDensity trend using the Count\_epoch setting would plot a value of 2 over the extent of that ten-second epoch).
- Perception\_epoch: yiel
  ds a graph of a sum of the designated comment
  ’
  s associated perception score(s) per user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a s
  i
  ngle ten-second epoch, one reading “xyz p=80” and the other “xyz p=120” then the EventDensity trend using the Perception\_epoch setting would plot a value of 200 over the extent of that ten-second epoch).
- Count\_sec: yields a graph of mean count of designate
  d comments per second for the user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-second epoch, then the EventDensity trend u
  s
  ing the Count\_sec setting would plot a value of 0.2
  –
  2 comments in the ten-second epoch divided by 10 seconds in one ten-second epoch-- over the extent of that ten-second epoch).
- Perception\_sec: yields a graph of the mean value (sum of comment perception v
  alues divided by number of comments) per second of the designated comment
  ’
  s associated perception score(s) per user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were pr
  e
  sent within the span of a single ten-second epoch, one reading “xyz p=80” and the other “xyz p=120” then the EventDensity trend using the Perception\_sec setting would plot a value of 20
  –
  2 comments in the ten-second epoch with summated perception values e
  q
  ual to 200, divided by 10 seconds in one ten-second epoch-- over the extent of that ten-second epoch).
- Count\_min: yields a graph of mean count of designated comments per minute for the user-specified epoch (e.g., if the comment “xyz” was specified, and epo
  ch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-second epoch, then the EventDensity trend using the Count\_min setting would plot a value of 12
  –
  2 comments in the ten-second epoch times 6 ten-s
  e
  cond epochs per minute-- over the extent of that ten-second epoch).
- Perception\_min: yields a graph of the mean value (sum of comment perception values divided by number of comments) per minute of the designated comment
  ’
  s associated perception score(s) per
  user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-second epoch, one reading “xyz p=80” and the other “xyz p=120” then the E
  v
  entDensity trend using the Perception\_min setting would plot a value of 1200
  –
  2 comments in the ten-second epoch with summated perception values equal to 200, times six 10 second epochs in one minute-- over the extent of that ten-second epoch).
- Count\_hour:
  yields a graph of mean count of designated comments per hour for the user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-sec
  o
  nd epoch, then the EventDensity trend using the Count\_hour setting would plot a value of 720
  –
  2 comments in the ten-second epoch times 6 ten-second epochs per minute time sixty minutes per hour-- over the extent of that ten-second epoch).
- Perception\_hour:
  yields a graph of the mean value (sum of comment perception values divided by number of comments) per minute of the designated comment
  ’
  s associated perception score(s) per user-specified epoch (e.g., if the comment “xyz” was specified, and epoch length wa
  s
  set to 10 seconds, and two comments with text “xyz” were present within the span of a single ten-second epoch, one reading “xyz p=80” and the other “xyz p=120” then the EventDensity trend using the Perception\_min setting would plot a value of 72000
  –
  2 co
  m
  ments in the ten-second epoch with summated perception values equal to 200, times six 10 second epochs in one minute, times 60 minutes per hour-- over the extent of that ten-second epoch)
- Count\_overlap: assigns a value of one comment count per second (or f
  raction thereof) over the segment the designated comment duration overlaps (this function utilizes information contained in the start and end times of the comment, i.e., the time segment the comment overlaps), then adds the resulting comment count seconds
  over the epoch and divides by epoch duration to yield an average comment count per second for the epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” were present within the span of a s
  i
  ngle ten-second epoch, one comment with duration of 2.5 seconds and the other with duration 5.5 seconds, then the EventDensity trend using the Count\_overlap setting would plot a value of 0.8
  –
  one comment times 2.5 seconds and one comment times 5.5 seconds
  yields 8.0 comment-seconds, divided by 10 seconds per epoch, giving the result of an average of 0.8 comments per epoch for that epoch-- over the extent of that ten-second epoch).
- Perception\_overlap: assigns the perception value of a comment to each second
  (or pro-rated perception to a fraction of a second) over the segment the designated comment duration overlaps (this function utilizes information contained in the start and end times of the comment, i.e., the time segment the comment overlaps), then summa
  t
  es the resulting perception values over the epoch and divides by epoch duration to yield an average perception per second for the epoch (e.g., if the comment “xyz” was specified, and epoch length was set to 10 seconds, and two comments with text “xyz” wer
  e
  present within the span of a single ten-second epoch, one comment with duration of 2.5 seconds and perception 120, and the other with duration 5.5 seconds and perception 80, then the EventDensity trend using the Perception\_overlap setting would plot a va
  l
  ue of 74
  –
  one comment times 2.5 seconds times 120, and one comment times 5.5 seconds times 80, yields 740 perception-seconds, divided by 10 seconds per epoch, giving the result of an perception average of 74 per second for that epoch-- over the extent of
  t
  hat ten-second epoch).

- User-adjustable parameters:
- - For EventDensity trend calculations: Epoch Duration (seconds), Event Text to be used as the basis for the graphical representation of comments containing matching text, source from which that text was
    derived (Any Origin, Insight, Recorded text, Recording change, or Detector), Sum Type method by which the comment will be graphically represented (note: to use the Perception\_... functions a designated comment “xyz” must follow the format “xyz p=x”, where
    p represents the perception variable and x is the perception value number attached to that comment): Count\_epoch, Count\_sec, Count\_min , Count\_hour Perception\_epoch, Perception\_sec, Perception\_min, Perception\_hour, Count\_overlap, Perception\_overlap, optio
    n
    al trend title
  - For EventDensity trend graph: x-axis duration (timescale), y-axis range, and color and optional fill color used for line graph
    .
- Parameter settings utilized in default trend examples (
  Trend Settings Version P15.mmx
  ) shipped with software: a
  n example EventDensity trend is included in the example file as the trend titled “Seizure Detections.” This trends sets the Epoch Duration to 1.0 seconds, the Event Text to “@SeizureDetected(Persyst)”, the Sum Type to Count\_overlap, and the y-axis range t
  o
  0-1.0.