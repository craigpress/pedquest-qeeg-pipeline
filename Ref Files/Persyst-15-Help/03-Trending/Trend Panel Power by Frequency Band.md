---
title: "Trend Panel: Power by Frequency Band"
source: persyst-15-help
section: "Trending"
htmFile: "Trend_Panel_Power_by_Frequency_Band.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Panel: Power by Frequency Band

# **Trend Panel: Power by Frequency Band**

The **Power by Frequency Band** trend panel configuration provides a collection (Panel) of trends that display the EEG power by band, e.g., Delta, Theta, Alpha, and Beta for Left Hemisphere and Right Hemisphere Channel Lists:

**FFT Power 1-4 Hz Left and FFT Power 1-4 Hz Right****:** Displays the FFT power from 1-4 Hz for Left Hemisphere and Right Hemisphere Channel Lists.

**FFT Power 4-8 Hz Left and FFT Power 4-8 Hz Right****:** Displays the FFT power from 4-8 Hz for Left Hemisphere and Right Hemisphere Channel Lists.

**FFT Power 8-13 Hz Left and FFT Power 8-13 Hz Right****:** Displays the FFT power from 8-13 Hz for Left Hemisphere and Right Hemisphere Channel Lists.

**FFT Power 13-20 Hz Left and FFT Power 13-20 Hz Right****:** Displays the FFT power from 13-20 Hz for Left Hemisphere and Right Hemisphere Channel Lists.

The FFT Power is calculated using an FFT Power trend (click here for details of the FFT Power trend implementation). The FFT Power is then averaged over a 2-minute period using a Time trend (click here for details of the Time trend implementation).

**Asymmetry, Relative Spectrogram (REASI Spectrogram)**: This spectrogram shows the difference between a left-hemisphere spectrogram and a right-hemisphere spectrogram (between homologous electrodes). This provides additional information about an asymmetry noted in the EASI/REASI index trends, e.g., at what frequency is the asymmetry most prominent? The vertical axis is frequency, and increasing asymmetry is indicated in red for right-weighted and blue for left-weighted. The color spectrum has been carefully selected to avoid color-preference, e.g., red doesn’t appear brighter/more intense than blue. (Click here for details of the REASI Spectrogram trend implementation.)

![image\44DTABTrend14Bs.gif](../assets/44DTABTrend14Bs.gif)