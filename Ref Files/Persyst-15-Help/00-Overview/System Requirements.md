---
title: "System Requirements"
source: persyst-15-help
section: "Persyst On-Line User's Guide"
htmFile: "Hardware_Specifications.htm"
tags:
  - persyst
  - persyst-help
  - overview
---

# System Requirements

# **System Requirements**

CPU: i5 processor or better  
Memory: 4 GB RAM or better  
Hard Disk: 2 GB free space or more  
OS: Windows 10 or Windows 11  
LAN: 1 GbE connection speed to file storage for review over local area network  
Antivirus exclusions for Persyst analysis files: \*.af1, \*.af2, \*.ar, \*.indx, \*.lay, \*.mg2, \*.mmx, \*.raw, \*.sd4, \*.xml 

Persyst 15 Seizure Detection using reduced set of electrodes and seizure burden shall be available as an application library on an Android platform with the following minimum requirements:

Android 8.0 (API Level 26)  
Processor: Qualcomm SDA660 (up to 2.2GHz)  
Memory: 4 GB LPDDR4X

Cybersecurity Information

The Persyst EEG Analysis Software has been designed with a strong focus on local security, minimal network exposure, and IT-managed compatibility. The following cybersecurity information is provided to assist clinical and IT personnel in securely installing, configuring, and maintaining the software.

1. Network and PHI Security  
- No internet connection is required for clinical operation.  
- All patient data (PHI) is processed and stored locally. No PHI is transmitted externally.  
- No login, password, or credential handling is implemented in the software.

2. Diagnostic Communication (Optional)  
- Persyst includes a background service that may send anonymous diagnostic logs or check for license updates.  
- This service uses outbound-only encrypted HTTPS (TLS 1.2+) to \*.persyst.com.  
- Users may disable this feature at any time via a setting in the application interface.  
- Disabling diagnostic communication has no impact on clinical functionality.

3. Software Updates and Integrity  
- Updates are distributed as digitally signed installers.  
- Automatic updates are not performed; installation is manual and IT-controlled.  
- The installer and core application binaries are code-signed to verify authenticity.

4. Antivirus Compatibility  
To avoid interference with EEG file processing, we recommend excluding the following file types from antivirus real-time scanning:  
.af1, .af2, .ar, .indx, .lay, .mg2, .mmx, .raw, .sd4, .xml

5. Additional Information  
For full cybersecurity recommendations, supported environments, and secure deployment guidelines, visit:

�� www.Persyst.com/security