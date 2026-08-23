---
title: "Persyst 15 Help File"
source: persyst-15-help
section: "Persyst On-Line User's Guide"
htmFile: "Persyst_14_Users_Guide.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# Persyst 15 Help File

# **Persyst 15 Help File**

Document Number 6219-05

**Persyst 15**

The software described in this book is furnished under a license agreement and may be used only in accordance with the terms of the agreement.

**Prescription Label**

![image\warning.gif](../assets/warning.gif "image\warning.gif") CAUTION: Federal law restricts this device to sale by or on the order of a physician or a licensed healthcare practitioner.

![image\warning.gif](../assets/warning.gif "image\warning.gif") CAUTION: This medical device is intended to be used exclusively by healthcare professionals.

**Warnings**

Note:  References in the warnings to seizure detection apply to both seizure detection and seizure probability, which are each output of the Persyst seizure detector.  See the discussion of seizure detection and seizure probability under Persyst EEG Trending.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Do not rely solely on the detectors for review of the study. The detectors are tools used to assist a qualified practitioner with the analysis and diagnosis of the patient.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Do not rely solely on the detectors for critical alerts or monitoring of a patient’s safety. The detectors should always be used in conjunction with other techniques such as (but not limited to) direct and remote surveillance and call buttons.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Persyst 15 provides notifications for seizure detection quantitative EEG, and aEEG that can be used when processing a record during acquisition. These include an on screen display and the optional sending of an email message. Delays of up to several minutes can occur between the beginning of a seizure and when the Persyst 15 notifications will be shown to a user. Persyst 15 notifications cannot be used as a substitute for real time monitoring of the underlying EEG by a trained expert.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: The seizure detector will not always detect seizures present in the record. Notifications for seizure detection, quantitative EEG, and aEEG using optional Email systems are not completely reliable and delivery cannot be guaranteed. Email may also introduce additional delays.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Persyst 15 Seizure Detection will detect a subset of electrographic seizures. It will also mark portions of a record that  
 do not represent electrographic seizures (false positives). It may not mark seizures of short duration, particularly focal character, or those with low amplitude. It has been assessed primarily with regards to seizures found in patients with epilepsy and may have lower detection rates with seizures having different characteristics. For all of these reasons Persyst 15 seizure detection cannot be substituted for expert review of the underlying EEG traces to determine the presence or absence of seizures in a patient’s record.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Since Persyst 15 seizure detection has not been tested with patients under 18 years old, we recommend that you verify the automatic seizure detections with another method.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: The Neonatal Seizure Detection component of Persyst 15 has been tested with neonatal patients’ (defined as near-term or term neonates of conceptional age between 36 and 44 weeks and less than two weeks of chronologic age). The Persyst 15 neonatal seizure detection algorithm has not been evaluated or tested in other age groups.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: The Persyst Imaging Workflow is not intended to provide diagnostic information. It is intended as an additional tool to aid in visualization. Review of the source images, EEG, and other patient information is recommended.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Since Persyst 15 spike detection has not been tested with newborns under one month old, we recommend that you verify the automatic spike detections with another method.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: The Suppression Ratio does not attempt to identify a burst suppression pattern.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Rhythmicity Spectrogram is a purely mathematical calculation of “Rhythmicity” and is not a clinically validated measure.

![image\warning.gif](../assets/warning.gif "image\warning.gif") WARNING: Notice to the User: Any serious incident that has occurred in relation to Persyst 15 EEG Review and Analysis Software should be reported to Persyst (manufacturer) and the competent authority of the Member State in which the user and/or patient is established..

![image\warning.gif](../assets/warning.gif "image\warning.gif") CONTRAINDICATION: Automatic event marking is not applicable to quantitative measures. These quantitative EEG measures should always be interpreted in conjunction with review of the original EEG waveforms.

![image\warning.gif](../assets/warning.gif "image\warning.gif") CONTRAINDICATION: Heart rate measurement of Persyst 15 is not applicable to patients with pacemaker and/or active implantable devices.

![image\warning.gif](../assets/warning.gif "image\warning.gif") CONTRAINDICATION: The automated event marking function of Persyst 15 is not applicable to aEEG.

![image\warning.gif](../assets/warning.gif "image\warning.gif") CONTRAINDICATION: The. Persyst 15 notifications cannot be used as a substitute for real time monitoring of the underlying EEG by a trained expert.

![image\warning.gif](../assets/warning.gif "image\warning.gif") CONTRAINDICATION: The Persyst sleep state output is subject to user confirmation via EEG waveform review and is not intended for the diagnosis of sleep disorders (e.g.: sleep apnea, narcolepsy, restless leg syndrome).

**Intended Purpose**

Persyst 15 EEG Review and Analysis Software is intended for the review, monitoring and analysis of EEG recordings made by electroencephalogram (EEG) devices to aid neurologists in the assessment of EEG. This device is intended to be used by qualified medical practitioners who will exercise professional judgment in using the information.

**Indications for Use**

1. Persyst 15 EEG Review and Analysis Software is intended for the review, monitoring and analysis of EEG recordings made by electroencephalogram (EEG) devices to aid neurologists in the assessment of EEG. This device is intended to be used by qualified medical practitioners who will exercise professional judgment in using the information.

2. The Seizure Detection and Seizure Probability component of Persyst 15 is intended to mark previously acquired sections of the adult (greater than or equal to 18 years) EEG recordings that may correspond to electrographic seizures, in order to assist qualified clinical practitioners in the assessment of EEG traces. EEG recordings should be obtained with a full scalp montage according to the standard 10/20 system. Alternatively, the Seizure Detection can operate using reduced set of electrodes including Fp1, F7, T3, T5, O1, Fp2, F8, T4, T6, O2, but will have decreased sensitivity for seizures due to its limited spatial sampling.

3. The Neonatal Seizure Detection component of Persyst 15 is intended to mark previously acquired sections of neonatal patients’ (defined as near-term or term neonates of conceptional age between 36 and 44 weeks and less than two weeks of chronologic age) EEG recordings that may correspond to electrographic seizures, in order to assist qualified clinical practitioners in the assessment of EEG traces. EEG recordings should be obtained with scalp-recorded EEG using the standard International 10-20 system electrode placement, modified for neonates (this includes electrode sites Fp1/2 or alternate F1/2, C3/4, T3/4, O1/2, and Cz, optionally including Fz). Alternatively, the Neonatal Seizure Detection component can operate using a more reduced set of electrodes including C3/4, Fp1/2 (F1/2), and O1/2 (recorded in such a manner to allow creation of montage C3-4, Fp1-O1, Fp2-O2), or an even more simplified electrode set including only C3/4 and Cz (arranged as C3-Cz and C4-Cz), but the three-electrode montage will have decreased sensitivity for seizures due to its limited spatial sampling.

4. The Spike Detection component of Persyst 15 is intended to mark previously acquired sections of the patient’s EEG recordings that may correspond to spikes, in order to assist qualified clinical practitioners in the assessment of EEG traces. The Spike Detection component is intended to be used in patients at least one month old. Persyst 15 Spike Detection performance has not been assessed for intracranial recordings.

5. Persyst 15 EEG Review and Analysis Software includes the Persyst Imaging Workflow (PIW), an imaging viewer. It is intended for use by qualified clinical practitioners on both adult and pediatric subjects at least 12 years of age to interpret EEG data in conjunction with any type of neuroimaging including magnetic resonance imaging (MRI) or computed tomography scans (CT). Persyst Imaging Workflow is not intended to provide diagnostic information.

6. The Persyst ESI component of Persyst 15 is intended for use by a trained/qualified EEG technologist or physician on both adult and pediatric subjects at least 3 years of age for the visualization of human brain function by fusing a variety of EEG information with rendered images of an individualized head model and an individualized MRI image.

7.The Persyst 15 sleep state feature provides the user with output concerning wake-sleep states (wake or sleep,) present in an EEG recording as an aid in assessing which states are present and when they are present. The EEG being assessed for sleep state should utilize standard 10-20 system electrode recording positions and contain the expected EEG patterns of typical wake and sleep, with no major persistent pathological alterations. The sleep state output is subject to user confirmation via EEG waveform review and is not intended for the diagnosis of sleep disorders (e.g.: sleep apnea, narcolepsy, restless leg syndrome). The sleep state feature is intended for adult and pediatric subjects at least 13 years and older.

8. Persyst 15 includes the calculation and display of a set of quantitative measures intended to monitor and analyze the EEG waveform. These include FFT, Rhythmicity, Peak Envelope, Artifact Intensity, Amplitude, Relative Symmetry, and Suppression Ratio. Automatic event marking is not applicable to the quantitative measures. These quantitative EEG measures should always be interpreted in conjunction with review of the original EEG waveforms.

9. Persyst 15 displays physiological signals, including the calculation and display of a heart rate measurement based on the ECG channel in the EEG recording, which are intended to aid in the analysis of an EEG. Heart rate measurement of Persyst 15 is not applicable to patients with pacemaker and/or active implantable devices.

10. The aEEG functionality included in Persyst 15 is intended to monitor the state of the brain. The automated event marking function of Persyst 15 is not applicable to aEEG.

11. Persyst 15 provides notifications for seizure detection, quantitative EEG and aEEG that can be used when processing a record during acquisition. These include an on screen display and the optional sending of an email message. Delays of up to several minutes can occur between the beginning of a seizure and when the Persyst 15 notifications will be shown to a user. Persyst 15 notifications cannot be used as a substitute for real time monitoring of the underlying EEG by a trained expert.

12.  Persyst 15 AR (Artifact Reduction) is intended to reduce EMG, eye movement, and electrode artifacts in a standard 10-20 EEG recording.  AR does not remove the entire artifact signal, and is not effective for other types of artifacts.  AR may modify portions of waveforms representing cerebral activity.  Waveforms must still be read by a qualified medical practitioner trained in recognizing artifact, and any interpretation or diagnosis must be made with reference to the original waveforms.

13. This device does not provide any diagnostic conclusion about the patient's condition to the user.

**Persyst 15 Clinical Benefits**

1.    Persyst 15 is intended for processing of previously acquired EEG and ECG waveform data for spike detection, seizure detection, quantitative EEG trending, heart rate trending, neuroimage co-registration and display, electrical source imaging, and for the review of those results in conjunction with the original EEG and ECG waveforms. 

2.    The software is able to display original EEG waveform data in a manner consistent with published guidelines, recommendations, or standards for EEG display and review. 

3.    The software is able to perform seizure detection either offline or in near real-time with sensitivity and specificity (false-positive rate) that meet or exceed the level of prior Persyst models, and that are consistent with or better than sensitivities and specificities reported for other seizure detection software marketed in the U.S.A. 

4.    The software is able to perform spike detection either offline or in near real-time with sensitivity and specificity (false-positive rate) that meet or exceed the level of prior Persyst models, and consistent with or better than sensitivities and specificities reported for other commonly used spike detection software marketed in the U.S.A. 

5.    The software is able to perform quantitative EEG trending either offline or in near real-time, and display the underlying time-synchronized EEG waveforms in conjunction with the quantitative EEG trends. Multiple quantitative EEG trends, including trends depicting EEG frequency analyses, amplitude analyses, and time averaged trends, are available to the device user for customization depending upon clinical circumstances. Graphical depictions of seizure and spike detection data are available for co-display with quantitative EEG trends and original EEG waveforms.

6.    The software is able to perform heart rate trending either offline or in near real-time and display the underlying time-synchronized EEG and ECG waveforms and quantitative EEG trends in conjunction with the heart rate trends. The heart rate trend feature functions at the level specified for heart rate analysis in “American National Standard - ANSI/AAMI EC13:2002 - Cardiac monitors, heart rate meters, and alarms.” 

7.    The software is able to perform sleep state using standard 10-20 system electrode placements, either offline or in near real-time, and display the underlying time-synchronized EEG waveforms in conjunction with the sleep state output. Graphical depictions of the sleep state feature’s output are available to the device user for co-display with quantitative EEG trends and original EEG waveforms. 

8.    The software includes Persyst Imaging Workflow (PIW), intended for use by a trained/qualified physician on both adult and pediatric subjects at least 2 years of age, to interpret EEG data in conjunction with any type of neuroimaging including magnetic resonance imaging (MRI) or computed tomography (CT). 

9.    Persyst 15 software includes a module called Persyst ESI (Electrical Source Imaging), powered by Epilog (Epilog NV), which provides the user a variety of EEG information with rendered images of an individualized head model and an individualized MRI image of a patient for visualization of some aspects of the patient’s brain function. 

10.    Persyst 15 can be paired with the Persyst Mobile application, which is accessible via a web browser or as an application on an iOS or Android device, which allows users to access EEG waveform and trending data, and seizure detection results, quickly and easily using an Internet-connected mobile device or computer. The Persyst Mobile application opens the EEG in read-only mode and cannot harm or modify the original record. The Persyst Mobile software does not control any system that is of potential harm to the patient. 

11.    Per the software’s intended use in processing of previously acquired EEG and ECG waveform data for spike detection, seizure detection, quantitative EEG trending, heart rate trending, sleep state, electrical source localization, and neuroimage display, and for the review of those results in conjunction with the original EEG and ECG waveforms, the analysis documented in the clinical evaluation shows that the risks associated with use of Persyst 15 are very low and are acceptable when weighed against the benefits to the patient. 

**Start-Up and Shutdown Procedure**

Start-up Procedure: Persyst 15 EEG Review and Analysis Software is launched by double-clicking on the Persyst 15 software icon on the Windows desktop. No additional startup procedure is required to launch the Persyst 15 software from the Windows desktop.  
  
Shutdown Procedure: Persyst 15 EEG Review and Analysis Software is safely shut down by closing Persyst using the “x” in the upper-right corner of the Persyst program window. Analysis results are saved automatically, or a prompt is provided to do so. No additional shutdown procedure is required to close the Persyst 15 software.

**Disclaimer**

All warranties of any kind are hereby disclaimed, express or implied, regarding the accuracy, sufficiency or suitability of this software, including all warranties of fitness for a particular purpose, for example, for clinical applications. The person utilizing this software has the sole responsibility for inspecting and making correct use of the results and images provided by this software. Any decisions taken on the basis of results provided by this software are at the risk and liability of the person utilizing the program. Persyst Development assumes no liability as a result of the use or application of this software.

**Copyright Notice**

Copyright © 1996-2025 Persyst Development LLC.

All Rights Reserved

No part of this publication may be copied without the express written permission of Persyst Development.

**Trademarks**

Windows is a registered trademark of
Microsoft ®
Corporation.

Other product names mentioned in this guide may be trademarks or registered trademarks of their respective companies and are hereby acknowledged.

Printed in the United States of America.