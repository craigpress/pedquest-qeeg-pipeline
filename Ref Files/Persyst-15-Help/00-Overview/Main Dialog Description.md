---
title: "Main Dialog Description"
source: persyst-15-help
section: "EEG Archive"
htmFile: "Main_Dialog_Box_Description.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# Main Dialog Description

# **Main Dialog Box Description**

![image\105Archive2.gif](../assets/105Archive2.gif)

**Options**

**Strip Patient Information**

Remove patient information from the archived file. .

**Export Entire Record**

Marked ranges to be clipped will be ignored (if present) and the entire recording will be archived.

**Clip/Export**

Select to generate the archive file.

**Advanced**

Select to display the full Archive Dialog options (below).

**Select Events for Clipping**

**(List)**

The **Events for Clipping** list allows single or multiple selections of events to be used when scanning the opened file. Events in the recording that match in text and origin with the Archive event will be included in the output file. To select an item, click the checkbox for that item and it will become selected. Click multiple items when you want to Archive multiple types of events.

**Add**

Clicking the [Add] button will open the Add/Edit Events Dialog for adding new events to the Archive Event list.

**Edit**

Clicking the [Edit] button opens the Add/Edit Events Dialog for editing the selected Event description. Note: only a single entry in the Archive Event List can be highlighted for the Edit button to become enabled.

**Delete**

Clicking the [Delete] button removes the selected Event description(s) from the Archive Event List. Note: a single entry or multiple entries in the Archive Event List must been highlighted for the Delete button to become enabled. If you click this button by accident, immediately click the CANCEL button in the Archive Tool’s main window and choose not to save your changes. Open the Archive Tool again to return your settings to their original values.

**Archive by Period**

**Periodic**

Selecting the [Periodic] options will allow periodic Archiving. For instance, setting 5 minutes every 60 minutes will result in an output file with five-minute epochs written every hour.

**Options**

**Select Channels**

Clicking the [Select Channels] button opens the Archive Channel Select Dialog allowing the user to include or exclude channels to be archived.

**V****ideo Trim**

Clicking the Video Trim button opens the Archive Video Trim Options Dialog allowing the user to set the audio quality for trimmed video segments.

**Use Montage (vs. Headbox) Data**

The [Use Montage (vs. Headbox) Data] button switches the mode of the Archive tool between writing Montage data and writing data using the original recorded reference. When checked, the output data will be written using the currently displayed montage and filter settings. Deselecting this option results in the original raw data being written with its original reference.

NOTE: If you write data using the Montage option, you will not be able to apply montages to the output file. It is not possible to apply montages to data that was written using the Montage option. Also, using the Montage option could result in the output of filtered data, if the currently displayed data has filters applied. Remember to deselect all filter settings if you want write Montaged data without filters applied.

**Compress file**

The [Compress file] checkbox switches the mode of the Archive tool between writing data with and without compression applied. When checked, the output data will be written using the currently selected compression settings. Deselecting this option results in the data being written without compression.

**Compress file: Options**

Once the [Compress file] checkbox has been checked, the [Options…] button can be clicked to open the Compression Dialog. See the help topic Compression Dialog Description for a full description of all compression options.

NOTE: If you write data using the Compression option, PARC will automatically filter the data at one half of the new sampling rate selected. For example, if you select an output sampling rate of 128 Hz, PARC will apply a High Frequency filter with a cutoff frequency of 64 Hz.

**32-****bit precision**

The standard Persyst Layout format writes EEG waveform data with 16-bit precision by default. Use this option for 32-bit precision. Note that only Persyst 14 or later supports the 32-bit Persyst Layout option.