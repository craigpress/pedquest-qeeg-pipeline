---
title: "Stored FFT Values and Invalid Trends"
source: persyst-15-help
section: "Trending"
htmFile: "Stored_FFT_Values_and_Invalid_Instruments.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Stored FFT Values and Invalid Trends

## **Stored FFT Values and Invalid Trends**

The data values (power spectrum, coherence and amplitude) calculated for each epoch are stored in the E
EG record’s directory u
sing the file extensions listed
below
. When you open a previously analyzed record, these values are automatically loaded and displayed.

• .lay

• .mg2

• .mg2.indx

• .sd4

• .ar

• .af1

• .af2

• .raw

The channels and frequency range for the values st
ored are determined by all the trends
defined (not just the active panel) when the analysis is started.

If at some later point you change
a trend
to utilize a channel not stored or a frequency range beyond that s
tored, then the trend
will display a “(?)” at the end of its name.

A trend
whose definition becomes invalid (e.g., on
e of the components of a Ratio trend
is deleted) will be displayed with an “(X)” at the end of its name. Newly defined
trends
that require values out of the stored range will require another analysis of the record: select **Clear**
and then **Process**
to
rescan the EEG recording.