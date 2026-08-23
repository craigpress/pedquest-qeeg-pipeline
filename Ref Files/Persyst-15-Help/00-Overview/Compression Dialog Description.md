---
title: "Compression Dialog Description"
source: persyst-15-help
section: "EEG Archive"
htmFile: "Compression_Dialog_Description.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# Compression Dialog Description

# **Compression Dialog Box Description**

![image\34Compress.gif](../assets/34Compress.gif)

**Compression options**

**(Slider)**

Use the Compression Dialog slider to select a new output-sampling rate for files written with the compression feature enabled. Down sampling of the input file is accomplished using linear decimation after applying an IIR low-pass filter with a cutoff frequency set at ½ the output sampling rate selected.

**Compression value**

This textbox displays the currently selected output-sampling rate. This will be the new sample rate of the any files written with the compression feature enabled.

**HiFilter cutoff**

This textbox displays the high frequency cutoff filter that will be applied before down sampling.

IMPORTANT: The high filter cutoff value will be ½ the sampling rate (Nyquist theorem). Therefore, when creating a 64 Hz file the data will be filtered with a 32 Hz low-pass filter. When reading the recording in Persyst, do not apply high frequency or notch filters with a value greater than ½ the sampling rate.

**OK**

Clicking the [OK] button will accept the current compression options selected in the dialog box.

**CANCEL**

Click the [CANCEL] button when you want to close the Compression dialog box without making any changes.