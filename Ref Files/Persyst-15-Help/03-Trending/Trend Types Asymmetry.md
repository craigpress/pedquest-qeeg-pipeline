---
title: "Trend Types: Asymmetry"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Types_Asymmetry.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Types: Asymmetry

# **Trend** **Types: Asymmetry**

**EEG Asymmetry Index (EASI)**
:
The Absolute Asymmetry Index trend (EA
SI, for EEG
Asymmetry
Index) uses a line graph to display an average of the absolute values, over a user-specified frequency range, of relative asymmetry data contained in the Relative Asymmetry Spectrogram as a function of time. Time is displayed on the x
-axis and percent absolute asymmetry on the y-axis.

Method: This graphical depiction of EEG
trend
data displays averaged values derived from the Relative Asymmetry Spectrogram calculations (which derive from a fast Fourier transform analysis performed on
the EEG signal). The following calculations generate the Absolute Asymmetry Index data for homologous electrode pairs:

First, the following vector is calculated (note: *Absolute*
version):

absrel() = abs() for Absolute versions and nop (note: nop equals No
OPeration) for Relative versions.

![image\ebx_1558227973.gif](../assets/ebx_1558227973.gif "image\ebx_1558227973.gif")

Using the result, the absolute asymmetry is calculated by summing the *S**i*
values over a user-specified frequency range and dividing by the number of frequency bins:

Absolute Asymmetry Index:

Imin is index of start of fr
equency range, Imax is index of end of frequency range

![image\ebx_-228836157.gif](../assets/ebx_-228836157.gif "image\ebx_-228836157.gif")

where j = 1, 2,…, M represents homologous electrode pairs (M=8 for bipolar longitudinal symmetry index with 8 bipolar channels per side),

i represents the index of bin i of an FFT power spectrum,

L= Left

R= Right

And ![image\ebx_1530232797.gif](../assets/ebx_1530232797.gif "image\ebx_1530232797.gif")
represents the Fourier amplitude (mcv) belonging to frequency bin i of the FFT power spectrum of the left portion of a homologous electrode pair with index=j.

Values for the absolute asymmetry index range from 0-100.

Note: Channel pairs are always homologous channels; different symmetry
trends
could be created using different groups (e.g., hemispheric, anterior, posterior, temporal, frontal, etc.) to assess particular regions.

- User-adjustable parameters:
- - For E
    EG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the FFT analysis will be performed: t
      he EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that an Absolute Asymmetry Index representing aggregations of channel data, as descri
      b
      ed above (e.g., a grouping of homologous channels for the left and right hemispheres to create an aggregate comparison of hemispheric EEG absolute asymmetry), can be displayed.
  - For FFT: sampling rate, points per window, window duration, windows per epoch,
    overlapped windows, and smoothing.
  - For Absolute Asymmetry Index graph: frequency range for which index should be calculated, EEG channel or channel group for homologous electrode comparisons (only left-sided channels need be specified; the homologous right
    -sided electrode pairing is automatically generated), x-axis duration (timescale), y-axis range (%), and color for line graph and optional color fill.
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: time constant = 0.16 seconds, high-frequency filter = 35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows per epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range -50-50 (%), frequency range for calculation of 1-18 Hz. Example trends display averages of FFT Spectrogram data from hemispheric comparisons (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1, Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2).

**Relative EEG Asymmetry Index (REASI):**
The Relative Asymmetry Index trend (REASI, for Relative EEG
Asymmetry
Index) uses a line graph to display an average of the signed values, over a user-specified frequency range, of relative asymmetry data contained in the Relativ
e Asymmetry Spectrogram, as a function of time. Time is displayed on the x-axis and percent relative asymmetry on the y-axis.

Method: This graphical depiction of EEG
trend
data displays averaged values derived from the Relative Asymmetry Spectrogram calcu
lations (which derive from a fast Fourier transform analysis performed on the EEG signal). The following calculations generate the Relative Asymmetry Index data for homologous electrode pairs:

First, the following vector is calculated (note: *Relative*
vers
ion):

absrel() = abs() for Absolute versions and nop (note: nop equals NoOPeration) for Relative versions.

![image\ebx_1558227973.gif](../assets/ebx_1558227973.gif "image\ebx_1558227973.gif")

Using the result, the relative asymmetry is calculated by summing the *S**i*
values over a user-specified frequency range and dividing by the number
of frequency bins:

Relative Asymmetry Index:

Imin is index of start of frequency range, Imax is index of end of frequency range

![image\ebx_-228836157.gif](../assets/ebx_-228836157.gif "image\ebx_-228836157.gif")

where j = 1, 2,…, M represents homologous electrode pairs (M=8 for bipolar longitudinal symmetry index with 8 bipolar cha
nnels per side),

i represents the index of bin i of an FFT power spectrum,

L= Left

R= Right

And ![image\ebx_1530232797.gif](../assets/ebx_1530232797.gif "image\ebx_1530232797.gif")
represents the Fourier amplitude (mcv) belonging to frequency bin i of the FFT power spectrum of the left portion of a homologous electrode pa
ir with index=j.

Values for the relative asymmetry index range from -100-100; relative asymmetry values weighted towards the left have a negative value.

Note: Channel pairs are always homologous channels; different symmetry
trends
could be created using
different groups (e.g., hemispheric, anterior, posterior, temporal, frontal, etc.) to assess particular regions.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-frequency filter, and Notch fil
      ter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the FFT analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG a
      cquisition equipment. Groups of channels can also be specified so that Relative Asymmetry Index representing aggregations of channel data, as described above (e.g., a grouping of homologous channels for the left and right hemispheres to create an aggregat
      e
      comparison of hemispheric EEG relative asymmetry), can be displayed.
  - For FFT: sampling rate, points per window, window duration, windows per epoch, overlapped windows, and smoothing.
  - For Relative Asymmetry Index graph: frequency range for which index shou
    ld be calculated, EEG channel or channel group for homologous electrode comparisons (only left-sided channels need be specified; the homologous right-sided electrode pairing is automatically generated), x-axis duration (timescale), y-axis range (%), and c
    o
    lor for line graph and optional color fill.
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: time constant = 0.16 seconds, high-frequency filter = 35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows per epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range -50-50 (%), frequency range for calculation of 1-18 Hz in one set of examples and 1-5 Hz and 6-14 Hz in other examples. Example trends display averages of FFT Spectrogram data from hemispheric comparisons (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1, Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2).

**Asymmetry, Relative Spectrogram (REASI Spectrogram)**
:
T
he Relative Asymmetry Spectrogram trend, using a density spectral array, displays a relative comparison of the power values of EEG data in homologous (left- and right-side position-mirrored) scalp electrodes, for each FFT frequency bin derived from a fast
Fourier transform analysis, as a function of time. Time is displayed on the x-axis, frequency on the y-axis, and a measure of relative EEG power for the user-specified channel(s) on the z-axis as a color scale.

Method: This graphical depiction of EEG
trend
data displays values derived from comparison of the power outputs of homologous EEG channels for each frequency bin generated by a fast Fourier transform analysis performed on the EEG signal. The following calculations generate the relative power data for
homologous electrode pairs:

Relative Asymmetry Spectrogram:

![image\ebx_1266158034.gif](../assets/ebx_1266158034.gif "image\ebx_1266158034.gif")

where j = 1, 2,…, M represents homologous electrode pairs (M=1 for a single homologous electrode pair; M=8 for bipolar longitudinal relative asymmetry spectrogram with 8 bipolar channels per
side),

i represents the index of bin i of an FFT power spectrum,

L= Left

R= Right

And ![image\ebx_1530232797.gif](../assets/ebx_1530232797.gif "image\ebx_1530232797.gif")
represents the Fourier amplitude (µV) belonging to frequency bin i of the FFT power spectrum of the left portion of a homologous electrode pair with in
dex=j.

Values for the relative asymmetry output calculation range from -100-100; relative asymmetry values weighted towards the left have a negative value, and those weighted toward the right have a positive value.

Note: Channel pairs are always homolo
gous channels; different relative asymmetry spectrogram trends can be created using different channel groups (e.g., hemispheric, anterior, posterior, temporal, frontal, etc.) to assess particular regions.

For example, if, for the F3-C3 channel configurati
on, the power value (Fourier amplitude) at a frequency of 6 Hz is 8 µV/Hz, and at 6 Hz is 4 µV/Hz for the homologous F4-C4 electrode, then the resulting relative asymmetry value for the 6 Hz frequency bin of that homologous electrode pair will be -50% (100
\*(4-8)/8). This would be painted as a blue tone (corresponding to -50) on the spectrogram for that time epoch at the 6 Hz value on the y-axis.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - Filter settings including time constant, high-fre
      quency filter, and Notch filter. These are set via the Trend Properties filter settings tab.
    - EEG analysis montage specifying channels on which the FFT analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites
      recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that Relative Asymmetry spectrograms representing aggregations of channel data, as described above (e.g., a grouping of homologous channels for the left and righ
      t
      hemispheres to create an aggregate comparison of hemispheric EEG relative asymmetry), can be displayed.
  - For FFT: sampling rate, points per window, window duration, windows per epoch, overlapped windows, and smoothing.
  - For Relative Asymmetry Spectrogram gr
    aph: EEG channel or channel group for homologous electrode comparisons (only left-sided channels need be specified; the homologous right-sided electrode pairing is automatically generated), x-axis duration (timescale), y-axis range (Hz), z-axis range (% r
    e
    lative asymmetry), and color palette used for z-axis relative asymmetry data.
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: time constant = 0.16 seconds, high-frequency filter = 35 Hz, FFT sampling rate = 64 Hz, FFT points per window = 128, FFT window duration = 2 seconds, FFT windows per epoch = 8, overlapped windows = On, FFT smoothing = 3, y-axis range 1-18 Hz, z-axis color palette uses two tone progressively varying blues (negative values, left-weighted asymmetry) to white (0% asymmetry) to red-browns (positive values, right-weighted) with scale ranging from -50-50%. Example trends display averages of FFT Spectrogram data from hemispheric comparisons (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1, Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2), anterior hemispheric (Fp1-F7, F7-T3, Fp1-F3, F3-C3, Fp2-F8, F8-T4, Fp2-F4, F4-C4), posterior hemispheric (T3-T5, T5-O1, C3-P3, P3-O1, T4-T6, T6-O2, C4-P4, P4-O2), parasagittal (Fp1-F3, F3-C3, C3-P3, P3-O1, Fp2-F4, F4-C4, C4-P4, P4-O2), and temporal channel groups (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp2-F8, F8-T4, T4-T6, T6-O2).