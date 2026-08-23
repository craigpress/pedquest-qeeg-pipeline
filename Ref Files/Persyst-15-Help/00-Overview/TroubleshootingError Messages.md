---
title: "Troubleshooting/Error Messages"
source: persyst-15-help
section: "EEG Archive"
htmFile: "Troubleshooting_Error_Messages.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# Troubleshooting/Error Messages

# **Troubleshooting/Error Messages**

**After opening the archive Tool and clicking the OK button I receive this error message:**

***“No events have been selected from the archive event list and Periodic has not been selected. Please select at least one event from the archive event list or Periodic before archiving.”***

This occurs when no events within the Event list have been highlighted or the periodic archive feature has not been selected. Make sure that you have at least one item in the Archive event list is highlighted or the period feature is enabled before clicking the OK button.

**After opening the archive Tool, clicking the Periodic check box, then clicking the OK button I receive this error message:**

***“You have asked to save X minutes out of every Y. Please adjust the periodic settings before continuing.”***

This occurs when you have entered a smaller value for the period of archiving, than the size of the window to archive. To correct this problem, modify the Periodic values entered so that the period length is larger than the window length.

**After opening the archive Tool, selecting some archive events and clicking OK, I receive this error message:**

***No events specified in the archive event list were found. Please check the archive event list and data file and retry the archive.***

You will receive this error message when the Archive Tool is not able to find any matches between the Archive Events selected and events in the recording. Verify that you have selected the correct Archive event from the event list and that the text and origin match at least one event in the recording that you are reviewing.

**After opening the archive Tool, selecting some archive events and clicking OK, entering an output name, then clicking the OK button I receive this error message:**

***The input and output filenames are the same. Please select a different output name before archiving.***

The Archive Tool will not allow you to overwrite an existing file with an archive file. Choose a different filename and click OK.