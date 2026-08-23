---
title: "Patient Selection"
source: persyst-15-help
section: "Multi Patient Monitor"
htmFile: "Patient_Selection_Manual.htm"
tags:
  - persyst
  - persyst-help
  - multi-patient-monitor
---

# Patient Selection

# **Patient Selection**

There are three patient selection options for the display cells:

**Manual:** Select a recording from the Persyst Database

**Automatic:** The next active recording is displayed automatically

**[Station Name]**: The display cell is assigned to an individual acquisition system name.

**Manual Selection**

The initial default configuration for Multi Patient Monitor is to display recordings that have been selected manually from the database list. If the cell is set to Manual mode then selecting the folder button in the middle of the cell will open the Open from Persyst Database dialog.

![image\101MPM1S.gif](../assets/101MPM1S.gif)

**Search Options**

**Unopened** **a****ctive** **r****ecords:** Recordings that are in progress and are not displayed in another MPM display cell.

**All a****ctive** **r****ecords:** Recordings that are in progress.

**Patient first name****,** **Patient last name****, File name,** or **All records** will search and list recordings accordingly.

**Browse file system** will launch a File Open dialog to locate and open individual recordings by file type.

![image\101MPM2S.gif](../assets/101MPM2S.gif)

As recordings are opened in each display cell the title bar will initially show **Active** on the right-end of the green title bar. As long as new EEG and trend data are detected and read by MPM then the title bar will remain green/Active for that recording.

If no new EEG and trend data is detected after the **Paused** timeout is reached then the title bar will change to orange and display Paused for that recording.

If no new EEG and trend data is detected after the **Stopped** timeout is reached then the title bar will turn to red and display Stopped for that recording.

**Automatic Selection**

Setting a display cell to “Automatic” will automatically load the next active recording that is detected in the recording location(s) configured in Persyst Database.

**Manual Selection**

Setting a display cell to a station name (e.g., EEG acquisition system name) will assign the selected cell to detect new active recordings that are started on the selected acquisition system.

![image\101MPM4.gif](../assets/101MPM4.gif)