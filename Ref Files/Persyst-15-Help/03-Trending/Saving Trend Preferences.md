---
title: "Saving Trend Preferences"
source: persyst-15-help
section: "Trending"
htmFile: "Saving_Trend_Preferences.htm"
tags:
  - persyst
  - persyst-help
  - trending
---

# Saving Trend Preferences

# **Saving Trend Preferences**

Click the **Preferences|Trend Preferences**
button on the
System Button Bar to
load a different set of panels and
trends
. The Panels,
trends
, and Analysis Engines are all stored in the \*.mmx file (the default set is stored in
“
Trend Settings Version P15.mmx
”
).

## **Editing the Trend Preferences**

Click the **Preferences|Modify Template**
button on the System Button Bar and then select an MMX to be edited. This will open an Editing instance of Persyst 14. Select Preferences|Trend Preferences to save your changes to the existing MMX file or to a newly named MMX file. The Panels, trends, and Calculation Engines are all stored in the \*.mmx file (the default set is stored in “Trend Settings Version P15.mmx”).

Note: If you are using Persyst Shared Settings (**Preferences|General Preferences|Support Files**
), then use a new name for your MMX file so that your changes will not be overwritten. To deploy a newly edited MMX file, the file should be uploaded to your Shared Settings UNC path. As OEM integrations can vary, please contact Persyst Support or your OEM EEG manufacturer for specific integration instructions for your EEG acquisition and review system.

## **Discarding Changes to the Trend Display**

If
Persyst 14
is closed without saving your changes then the Trend Panel configuration
for that EEG record will have your changes saved to a file in the EEG recording folder, e.g.,
\\YourHospital\EEGServer\jane.doe.eeg.mmx
”. When you open the recording again, your changes will be retained. This “record-specific” MMX can be used as a Trend Template by copying it to your local ProgramData\Persyst folder.

To revert to the original trend settings, select **Preferences|Trend Preferences**
and then **Open**
the original Trend Template (mmx) file.