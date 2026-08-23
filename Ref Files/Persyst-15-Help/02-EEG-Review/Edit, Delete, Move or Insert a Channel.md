---
title: "Edit, Delete, Move or Insert a Channel"
source: persyst-15-help
section: "EEG Review"
htmFile: "Edit_Delete_Move_or_Insert_a_Channel.htm"
tags:
  - persyst
  - persyst-help
  - eeg-review
---

# Edit, Delete, Move or Insert a Channel

### **Edit, Delete, Move or Insert a Channel**

Click **Edit** from the Context menu. If only a single channel is selected, the dialog will allow you to change the channel name as well as the G1 and G2 grids.

![image\edit_channel_1.gif](../assets/edit_channel_1.gif)

Click **Delete** from the Context menu to remove the selected channels from the montage. Click **Move** to reposition the channels up or down in the display order.

Click **Insert** to insert a new channel before the selected channel. You will be prompted with the **Edit Channel(s)** dialog so that you can define the new channel.

A **Polygraph Control** section is provided in the **Channel Edit** dialog. Use this for your montage channels with any DC input (e.g., SaO2, heart rate, blood pressure, etc.).

![image\polygraph_edit.gif](../assets/polygraph_edit.gif)

The Polygraph Control provides minimum and maximum scaling control to allow changes in DC inputs with small variation, e.g., SaO2, to be clearly resolved. **Show Scaling** can be enabled to provide numeric data as well, placing the instantaneous value for the trace between the scale’s minimum and maximum values.

DC Channels can be calibrated off-line; during acquisition, record a “zero” (or other minimum) set-point for several seconds, then a maximum (e.g., 100%) set-point for several seconds. Then from the EEG page, use cursors to mark the “Calibration” and “Offset” calibration set-points to save your DC channel calibration.

Select **Downsample** to reduce the frequency at which Persyst analysis tools will analyze any channel. This can speed processing for channels that do not contain high frequency information of interest (e.g., frequencies of interest should be no higher than ½ the sampling rate).

![image\edit_channel_1AR.gif](../assets/edit_channel_1AR.gif)

The **Artifact** tab provides options to control Artifact Reduction for individual channels. This option is for use with the Trend Montage: Electrode Artifact detection and reduction will automatically exclude channels from trends for individual Channels and Channel Lists. **Compute** is the default selection. Selecting **Always Good** or **Always Bad** will set the channel’s state manually.