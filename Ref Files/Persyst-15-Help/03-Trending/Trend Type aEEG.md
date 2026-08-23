---
title: "Trend Type: aEEG"
source: persyst-15-help
section: "Trending"
htmFile: "Instrument_Type_aEEG.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Trend Type: aEEG

# **Trend** **Type: aEEG**

The aEEG trend displays the amplitude characteristics of a filtered, rectified representation of the EEG signal as a function of time. Time is displayed on the x-axis and the aEEG amplitude measure on the y-axis. The aEEG trend provides a simplified depiction of amplitude characteristics of the EEG signal, and is intended to be used in conjunction with other EEG trends, and with the original EEG waveforms, for analysis of the EEG.

Method: This graphical depiction of EEG
trend
data displays values derived via the following method, which emulates the method used in the original Cerebral Function Monitor. The existing EEG waveform (as recorded by OEM EEG equipment being used to acquire the EEG signal) is first downsampled to a rate of 64 samples/second, then filtered using a 60 Hz notch filter and an asymmetrical filter that emulates the asymmetrical filter utilized by Maynard and colleagues in the original Cerebral Function Monitor. The asymmetrical filter implemented in the Persyst aEEG function has a frequency-response output as shown in Figure 1. Figure 1 also shows the asymmetrical filter specifications for the original Cerebral Function Monitor described by Maynard and colleagues.1 The measured Persyst aEEG asymmetrical filter frequency-response curve is approximately identical to the specifications of the original Cerebral Function Monitor.

![image\123aEEG.gif](../assets/123aEEG.gif "image\123aEEG.gif")

Following application of the asymmetrical filter, the result is rectified. Then, a low-pass filter (time constant equals 0.5 seconds) is applied, and the output is multiplied by a calibration factor so that the peak-to-peak amplitude is output. The aEEG trend is plotted on a linear y-axis scale from 0 to 10 µVpp and a logarithmic scale from 10 to 100 µVpp. Output from 1 second epochs of the aEEG calculation are plotted as a minimum-maximum bar graph (i.e., for each one-second epoch of EEG, the minimum and maximum aEEG values are plotted and joined by a vertical line) to approximate the graphical appearance of the output of the original Cerebral Function Monitor. The user is able to vary the time scale used on the x-axis of the aEEG trend, which is plotted on the same x-axis time scale as any other user-specified EEG trends that are simultaneously displayed.

- User-adjustable parameters:
- - For EEG signal to be analyzed:
  - - EEG analysis montage specifying channels on which the aEEG analysis will be performed: the EEG montages that can be specified are limited to the original EEG sites recorded utilizing OEM EEG acquisition equipment. Groups of channels can also be specified so that aEEG graphs representing statistical aggregations of channel data, such as the average of values from several channels (e.g., a grouping of channels for the left hemisphere or the anterior left hemisphere), can be displayed.
  - For aEEG graph: x-axis duration (timescale), graph line color
    .
- Parameter settings utilized in default trend examples (Trend Settings Version P15.mmx) shipped with software: Example aEEG trends display averages of aEEG data from the left hemisphere (Fp1-F7, F7-T3, T3-T5, T5-O1, Fp1-F3, F3-C3, C3-P3, P3-O1) and right hemisphere (Fp2-F8, F8-T4, T4-T6, T6-O2, Fp2-F4, F4-C4, C4-P4, P4-O2).

References:

Maynard D, Prior PF, Scott DF. Device for continuous monitoring of cerebral activity in resuscitated patients. Br Med J. 1969;4(5682):545–546.

Maynard D, Prior PF, Scott DF. A continuous monitoring device for cerebral activity. Electroencephalogr Clin Neurophysiol. 1969;27(7):672–673.

Prior P, Maynard DE. Monitoring cerebral function: long-term recordings of cerebral electrical activity. Elsevier/North-Holland Biomedical Press; 1979.

Prior PF, Maynard DE. Technical and Practical Aspects of Monitoring. In: Monitoring Cerebral Function: Long-Term Monitoring of EEG and Evoked Potentials. Amsterdam;New York;
Oxford: Elsevier; 1986:85–140.