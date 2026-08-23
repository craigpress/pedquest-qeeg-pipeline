---
title: "Add/Edit Events Dialog Description"
source: persyst-15-help
section: "EEG Archive"
htmFile: "Add_Edit_Events_Dialog_Box_Description.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# Add/Edit Events Dialog Description

# **Add/Edit Events Dialog Box Description**

![image\32AddEdit.gif](../assets/32AddEdit.gif "image\32AddEdit.gif")

**Text**

Click
in the [Text] entry box to add or modify an existing Event Text description.
The entered text will be used when searching through the events of the
EEG
file
you are viewing. Event text that matches this search text will be written
in the output files with [Before] seconds of data before the event and
[After] seconds of data after the recorded event.

The
wildcard “\*” can be used for more complicated search filters. For instance,
entering
“@Vplot\*” will allow matching of any event text which begins with “@Vplot”
(i.e. @Vplot g=2 p =0, @Vplot g=4 p =1, etc.).

Note:
The “@” symbol does not modify the archive. It is used as a prefix to
group events alphabetically in the Persyst Comment List.

**Origin**

Select
a particular [Origin] of the search text to be used when scanning the
EEG file you are viewing. Event text in the recorded
data must match in origin for it to be included in the Archive. Below
are the available Origin choices and an explanation for each choice:

User-Persyst

Only
text comments entered by using the Persyst
program
and matching the Event Text will be included in the output file.

User-Recording
System

Only
event text entered during the original recording and matching the Event
Text will be included in the output file.

Equipment
Events

Only
event text denoting recording changes entered during the original recording
and matching the Event Text will be included in the output file.

**Detections-Persyst**

Only
events added by Detector and matching the Event Text will be included
in the output file.

**Any
Origin**

Event
text from any source and matching the Event Text will be included in the
output file.

**Before
(s)**

Use
the [Before] second selection box for specifying the amount of data to
write before the matching event occurred. For instance, entering 60 will
write 1 minute of data before any events that match the Event Text and
Origin criterion.

**After
(s)**

Use
the [After] second selection box for specifying the amount of data to
write after the matching event occurred. For instance, entering 180 will
write 3 minutes of data after any events that match the Event Text and
Origin criterion.

**Archive
Video**

If
this option is selected, then
accompanying video will be archived with the portions of EEG marked
with
the Event Text.

**OK**

Click
[OK] when you happy with any changes you have made. This will close the
Add/Edit Events Dialog.

**CANCEL**

Click
[CANCEL] when you want to close the Add/Edit Events Dialog without
making any changes.