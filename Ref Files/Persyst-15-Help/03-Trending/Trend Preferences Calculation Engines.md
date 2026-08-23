---
title: "Trend Preferences: Calculation Engines"
source: persyst-15-help
section: "Trending"
htmFile: "Calculation_Engines.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Preferences: Calculation Engines

# **Calculation Engines**

Calculation Engines perform the calculations used by the trends. Trends are combined to create a panel of trends.

![image\53Engine.gif](../assets/53Engine.gif)

For example, to display an FFT Spectrogram trend (e.g., CSA), an FFT Engine must first be available in the list of Calculation Engines. Only then can you create an FFT Spectrogram trend that specifies the channels to be scanned, the color of the trends, the frequency range and scaling.

Persyst 14 is pre-configured with a default set of trend panels, trends, and Calculation Engines. You can change or add additional Calculation Engines, e.g., if FFT parameters other than the default options is desired.

The creation of multiple Calculation Engines allows the display of trends based on different calculations (e.g., FFT, Rhythmicity, etc.) and with different sampling rates (epoch durations). Each engine can be assigned its own attributes by selecting it and pressing Edit. When a new trend is created, it is attached to the first valid Engine in the list. For example, an FFT\_Spectrogram will be attached to the first FFTEngine in the list. The Engine list order can be changed with the Up/Down buttons.

The available Calculation Engine types allow a greater variety of analysis options including:

- Amplitude: Display various parameters taken from the raw EEG waveforms.
- aEEG: Performs calculations for the aEEG trends.
- FFT: Performs calculations for the frequency trends and determines the FFT calculation parameters.
- Rhythmicity: Performs calculations for the Rhythmicity Spectrograms and determines the rhythmicity calculation parameters.
- Peak Envelope: Performs calculations for the Peak Envelope trends and determines the frequency ranges and epoch length.
- Artifact (various): Calculation and display of electrode and physiological artifact and Artifact Reduction in the EEG trend display.
- Seizure Probability P1401: Performs Persyst seizure detection.
- Spike Density V101 Performs Persyst spike detection.
- Heart Rate: Calculates Heart Rate based on the ECG channels selected.
- CNS Monitor Engine: Provides access to monitoring data recorded by the CNS Monitor from CNS Technology, Inc.