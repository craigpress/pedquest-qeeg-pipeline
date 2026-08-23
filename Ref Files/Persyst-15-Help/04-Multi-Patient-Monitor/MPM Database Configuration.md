---
title: "MPM Database Configuration"
source: persyst-15-help
section: "Multi Patient Monitor"
htmFile: "MPM_Database_Configuration.htm"
tags:
  - persyst
  - persyst-help
  - multi-patient-monitor
---

# MPM Database Configuration

# **MPM Database Configuration**

T
he Persyst Database is used by Multi Patient Monitor (MPM) to index and select EEG recordings for display
.
The Database settings are shared between
Persyst 15 and MPM,
therefore
the instructions below describe
the configuration within
Persyst 15 and MPM
.

![image\100MPMDatabase14Bs.gif](../assets/100MPMDatabase14Bs.gif)  
*Persyst Database* *display* *within* *Persyst 14*

![image\100MPMDatabase6.gif](../assets/100MPMDatabase6.gif)  
*Persyst Database display within Multi Patient Monitor*

**Initial configuration within** **Persyst 14****:**

The Persyst Database is enabled and configured by selecting **Preferences**
, **General Preferences**
, and then the **Database**
tab.

![image\100MPMDatabase14B0.gif](../assets/100MPMDatabase14B0.gif)

Select **Use Persyst Database**
and then select **Add**
to add locations and EEG file types.

![image\100MPMDatabase14B1b.gif](../assets/100MPMDatabase14B1b.gif)

When browsing to network file locations use a UNC (e.g.,
\\server
name\\folder name). Do not use mapped drives for the file path or the EEG recordings will not be listed in the Persyst Database.

![image\100MPMDatabase2.gif](../assets/100MPMDatabase2.gif)

Note: If EEG recordings are not listed in the Persyst Database then the PSLocator.log file will list any error messages that were encountered. From the Database configuration tab, select **Advanced Configuration**
and then select **Show**
to view the contents of the PSLocator.log file.

![image\100MPMDatabase3.gif](../assets/100MPMDatabase3.gif)

The default selection for the Windows service account is the Local System account. If the network location(s) for EEG recordings require a different User Name and Password to access these locations
,
then this can be configured through Windows Services. Restart the Persyst Locator Service after selecting a new Log On account.

![image\100Locator2.gif](../assets/100Locator2.gif)

![image\100Locator1.gif](../assets/100Locator1.gif)

After the Persyst Database is enabled and configured, it will list EEG recordings at each of the file formats and locations listed. Select the **Open**
button from the
Persyst 14
System Bar to launch the Persyst Database. Select a recording and then **OK**
. Alternatively, use the **Browse file system**
button to open recordings directly from the file system.

![image\100MPMDatabase14Bs.gif](../assets/100MPMDatabase14Bs.gif)

**Database configuration within Multi Patient Monitor:**

The Persy
st Database within Multi Patient Monitor can be configured or edited from the Multi Patient Monitor display
by selecting
the **Settings**
button in the upper-right corner of the MPM display and then selecting the **Locations**
tab.

![image\100MPMDatabase7.gif](../assets/100MPMDatabase7.gif)

Select **Add**
or **Modify**
for new file locations or file types.

Select **Delete**
to remove a file location. Alternatively, a location can be made inactive by de-selecting the **Active**
option for the file location. Use this option if a file location will be used intermittently.

![image\100MPMDatabase8.gif](../assets/100MPMDatabase8.gif)