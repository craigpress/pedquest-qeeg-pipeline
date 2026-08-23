---
title: "Detection Parameters"
source: persyst-15-help
section: "Previous-Generation Detector (Reveal)"
htmFile: "Detection_Parameters.htm"
tags:
  - persyst
  - persyst-help
  - reveal
---

# Detection Parameters

### **Detection Parameters**

Reveal uses *Scan Protocols* to save custom settings for scanning recordings that require special settings, e.g., recordings with unusual gains or those with non 10-20 electrode names/configurations. To create a custom Protocol, select **Settings|Protocol** from the Reveal menu.

Recording quality and environment can affect spike and seizure detection performance. Click HERE for information on the performance characteristics of Persyst Seizure Detection.

The Event Settings dialog provides three tabs for customizing Reveal’s detection parameters:

**SpikeMontage:** Spike detection channels, modifiers (Eyeblink or Temporal), sensitivity for channels with significantly higher or lower amplitudes than the other channels, detection reference, and filters.

**RhythmicBurstMontage:** Spike detection channels, modifiers (Eyeblink or Temporal), sensitivity for channels with significantly higher or lower amplitudes than the other channels, detection reference, and filters.

**Settings:** Detection sensitivity for Spike, SpikeBurst, RhythmicBurst events. Includes separate detection/duration settings for notifications.

**Spike Montage**

![image\detection_parameters_1.gif](../assets/detection_parameters_1.gif)

**Apply Montage:** Select a montage saved in Persyst EEG Review for scanning in Reveal (see the help topic Create a New Montage). This can be used to present a list of extra-10-20 or numbered channel labels for scanning with Reveal. **Always Use G2** will allow use of bipolar scanning montages (referential is recommended spike localization and mapping).

**From EEG Page:** Used when scanning recordings with unusual (very low or very high) gains. Reveal will use the display sensitivity *selected in Persyst EEG Review* as the scanning sensitivity. To use this option, the display sensitivity in Persyst should be set to display the traces as you would normally review them.

**Automatic:** Default is “selected”. Enables linear Neural Network that automatically sets the Sensitivity (uV/mm). The first three minutes of EEG are used to calculate the sensitivity, and the calculation is robust to the presence of artifact and/or calibration (providing this makes up less than 50% of the first 3 minutes). To see the automatic sensitivity setting, pause scanning, then select **Settings|Protocol**. If the recording is less than 3 minutes in length, **File|AutoEnd** must be selected so that the calculation uses the existing record length.

**Sensitivity:** Used when **Automatic** is de-selected *and* when scanning recordings with unusual (very low or very high) gains. Reveal will use the display sensitivity you select as the scanning sensitivity.

**Low/High/Notch filter:** Filters selected for the scanned EEG. Use the **Notch Filter** if the recording has excessive line noise. Changing Low or High filters may adversely affect detection accuracy, e.g., a more restrictive low filter may attenuate slow waves appearing after a spike event, decreasing its detection probability.

**Use Scalp Sign** and **Use 1020 Topology**. In general, these options should be *on* for 10-20 recordings and *off* for non 10-20 recordings. **Use Scalp Sign** does not dramatically change the spikes that are marked, but it does result in the marked focal points better matching what human readers mark (i.e., a preference for scalp negative components). **Use 1020 Topology** now replaces use of the channel Code (Temporal, Eyeblink, etc.). Turn this feature *off* if you don’t want to treat channels preferentially.

**Always Use G2** will allow use of bipolar scanning montages (referential is recommended spike localization and mapping).

**Select All:** Used to make changes to all channels.

**Edit Selected:** Turn channels on/off, select individual scan sensitivity, and apply Eyeblink or Temporal filters.

**Reference:** Select the scanning reference.

**Rhythmic Burst Montage**

![image\detection_parameters_2.gif](../assets/detection_parameters_2.gif)

**Apply Montage:** Select a montage saved in Persyst for scanning in Reveal (see the Persyst help topic Create a New Montage). This can be used to present a list of extra-10-20 or numbered channel labels for scanning with Reveal. **Always Use G2** will allow use of bipolar scanning montages (bipolar montages tend to restrict artifact to the affected channels, and will not affect localization/mapping of individual seizure events).

**From EEG Page:** Used when scanning recordings with unusual (very low or very high) gains. Reveal will use the display sensitivity *selected in* *Persyst EEG Review* as the scanning sensitivity. To use this option, the display sensitivity in Persyst should be set to display the traces as you would normally review them.

**Automatic:** Default is “selected”. Enables linear Neural Network that automatically sets the Sensitivity (uV/mm) for any range of EEG activities. The first three minutes of EEG are used to calculate the sensitivity, and the calculation is robust to the presence of artifact and/or calibration (providing this makes up less than 50% of the first 3 minutes). To see the automatic sensitivity setting, pause scanning, then select **Settings|Protocol**. If the recording is less than 3 minutes in length, **File|AutoEnd** must be selected so that the calculation uses the existing record length

**Sensitivity:** Used when scanning recordings with unusual (very low or very high) gains. Reveal will use the display sensitivity you select as the scanning sensitivity.

**Low/High/Notch filter:** Filters selected for the scanned EEG. Use the **Notch Filter** if the recording has excessive line noise. Changing Low or High filters may adversely affect detection accuracy, e.g., a more restrictive low filter may attenuate slow waves, and a less restrictive high filter may obscure electrographic seizure activity coincidental with artifact from clinical seizure activity.

**Always Use G2** will allow use of bipolar scanning montages.

**Select All:** Used to make changes to all channels.

**Edit Selected:** Turn channels on/off, select individual scan sensitivity, and apply Eyeblink or Temporal filters.

**Reference:** Select the scanning reference (referential montages only).

**Settings**

![image\scan_reveal_5.gif](../assets/scan_reveal_5.gif)

**Perception Minimum (Detect):** Detection sensitivity that sets the minimum perception (a belief probability that the event is a spike, spike burst, or rhythmic burst). Lower values will increase sensitivity. The default settings are suitable for a wide range of recording types/environments.

**Perception Minimum (Notify):** Allows different sensitivity settings for notifications (e.g., audible/visual/relay box). Typically these will be made less sensitive (higher perception setting) than the Detect settings based on the care environment.

**Duration Minimum (Detect):** The minimum duration (in seconds) for seizure events: **Spike Burst** and **Rhythmic Burst** detections. Lower values will increase sensitivity. The default settings are suitable for a wide range of recording types/environments.

**Duration Minimum (Notify):** Allows different sensitivity settings for notifications (e.g., audible/visual/relay box). Typically these will be made less sensitive (higher perception setting) than the Detect settings based on the care environment.

**Save Custom Protocols**

Select **Settings|Save Protocol** from the Reveal menu to save your custom protocols.

![image\scan_reveal_6.gif](../assets/scan_reveal_6.gif)