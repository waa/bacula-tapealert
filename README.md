# BACULA TAPEALERT
This `bacula-tapealer.py` script is a drop-in `tapealert` script replacement which automatically identifies the correct `sg` device node to test with the tapeinfo utility.

## INTRODUCTION:

The Bacula Storage Daemon (SD) 'Device{}' resource provides two settings which may be used to allow the SD to automatically check a tape drive device for any 'TapeAlert' messages at two times:

- After a job finishes and the tape drive is idle
- After each read or write error on the drive

Any TapeAlert messages reported are then logged into the Job log.

Depending on the type of TapeAlert message(s) reported, the SD can then act on the alert and disable a volume in the catalog, disable a faulty or failing tape drive device, and even fail the Job.

The two SD device configuration settings to enable this feature are:

- ControlDevice = /dev/sg4
- AlertCommand = "/opt/bacula/scripts/tapealert %l"

Historically, the `ControlDevice` would be set to a tape drive device's SCSI Generic (SG) node. For example: `/dev/sg4`

The AlertCommand is typically set to point to the `/opt/bacula/scripts/tapealert` sample bash script which is shipped with Bacula, and the `%l` represents the "archive control channel name" (ie: ControlDevice) that will be passed to the AlertCommand script.

## THE PROBLEM:

A tape drive's SG node may change after a reboot, depending on when the kernel identifies and enumerates it. This represents a problem since the Bacula SD's Tape Drive resource configurations (including this ControlDevice setting) are usually set once during configuration and then left.

If the ControlDevice setting is pointing to the wrong SG node, the TapeAlert feature in the Bacula SD will not function properly, because the AlertCommand script will be called with the wrong SG node to test.

## THE SOLUTION:

This `bacula-tapealert.py` drop-in replacement script! :)

This script is able to automatically determine the *current* and correct SG node device for the tape drive on-the-fly.

When using this script in place of the `/opt/bacula/scripts/tapealert` script, the ControlDevice should be set to the same tape drive device node as specified in the `ArchiveDevice` setting.

For example:
```
ArchiveDevice = /dev/tape/by-id/scsi-350223344ab000900-nst
ControlDevice = /dev/tape/by-id/scsi-350223344ab000900-nst
AlertCommand = "/opt/bacula/scripts/bacula-tapealert.py %l logging test" *see notes about command line options below
```

## INSTALLATION, CONFIGURATION, AND USE:

### Installation:
To use this script in place of the default `/opt/bacula/scripts/tapealert` script, copy it to '/opt/bacula/scripts', set it executable, and set the owner to the user that the Bacula SD runs as (typically 'bacula'):
```
# cp bacula-tapealert.py /opt/bacula/scripts
# chmod u+x /opt/bacula/scripts/bacula-tapealert.py
# chown bacula:bacula /opt/bacula/scripts/bacula-tapealert.py
```

### Configuration:
Next, configure the SD's tape drive device resources with the additional `ControlDevice` and `AlertCommand` settings as described above.


### Use:
The following command line options may be used after the `%l` on the AlertCommand line:
```
# /opt/bacula/scripts/bacula-tapealert.py -h
Usage:
bacula-tapealert.py <drive_device> [logging] [-f <logfile>] [test] [debug]
bacula-tapealert.py -h | --help
bacula-tapealert.py -v | --version

Options:
drive_device   The drive's /dev/sg*, /dev/nst#, or /dev/tape/by-id/*-nst, or /dev/tape/by-path/* node.
test           Run in test mode? Edit the 'fake_tapeinfo_txt' string in this script to suit.
debug          Log a lot more output, including system utility outputs.
logging        Should the script log anything at all? Default is False!

-f <logfile>   Where should the script append log file to? [default: /opt/bacula/working/bacula-tapealert-py.log]

-h, --help     Print this help message.
-v, --version  Print the script name and version.
```

### Testing:

#### Command Line Testing:
Before running this script in production, the following tests should be run to be sure that it is configured and working as expected in your environment.

First, run the script from the command line:

- Identify the ArchiveDevice setting in your SD tape drive device.

We will use the `/dev/tape/by-id/scsi-350223344ab000900-nst` from the configuration example above.

- Next, run the script, adding the `test` and `logging` command line options:

\# /opt/bacula/scripts/bacula-tapealert.py /dev/tape/by-id/scsi-350223344ab000900-nst logging test 

- When run with these two options, the `test` option will tell the script to ignore the device parameter, and instead use the sample `tapeinfo` output included in the script in the `fake_tapeinfo_txt` variable. This text variable contains some example `TapeAlert` lines that might be included in a tapeinfo output.

Additionally, the `logging` parameter enables logging to a file (default /opt/bacula/working/bacula-tapealert-py.log). Without this option, the script does not log anything.

The output you should see when run the with above command line should be:
```
TapeAlert[1]
TapeAlert[2]
TapeAlert[3]
TapeAlert[5]
TapeAlert[13]
TapeAlert[20]
TapeAlert[21]
```

- Because the `logging` command line variable was included, the following will appear in the /opt/bacula/working/bacula-tapealert-py.log file:
```
2024-03-07 19:19:32 | ----------[ Starting /mnt/bta/bacula-tapealert.py v0.04 ]----------
2024-03-07 19:19:32 | Drive Device: /dev/tape/by-id/scsi-350223344ab000900-nst
2024-03-07 19:19:32 | The 'test' variable is True. Testing mode enabled!
2024-03-07 19:19:32 - WARN: 7 TapeAlerts found for drive device /dev/tape/by-id/scsi-350223344ab000900-nst (Testing mode enabled. These example results are bogus.):
2024-03-07 19:19:32 -       [1]: Read: Having problems reading (slowing down).
2024-03-07 19:19:32 -       [2]: Write: Having problems writing (losing capacity).
2024-03-07 19:19:32 -       [3]: Hard Error: Uncorrectable read/write error.
2024-03-07 19:19:32 -       [5]: Read Failure: Tape faulty or tape drive broken.
2024-03-07 19:19:32 -       [13]: Snapped Tape: The data cartridge contains a broken tape.
2024-03-07 19:19:32 -       [20]: Clean Now: The tape drive neads cleaning NOW.
2024-03-07 19:19:32 -       [21]: Clean Periodic:The tape drive needs to be cleaned at next opportunity.
| ----------------------------------------------------------------------------------------------------
| Bacula TapeAlert - v0.04 - bacula-tapealert.py - By: Bill Arlofski waa@revpol.com (c) March 07, 2024
```
Note: When in testing mode, you are warned that the script is in test mode and that the results are bogus.


#### Testing with the Storage Daemon:

Now that the script is working as expected, it is time to test with the Storage Daemon by running a job which uses this tape drive device.

Because the `test` command line option should still be in the SD's tape device configuration, we can just run a job:
```
* run yes job=Linux-Etc-L80-Every4Mins
```

Here is the Job log.
```
07-Mar 19:29 ol9-sd JobId 25958: 3304 Issuing autochanger "load Volume G03037TA, Slot 37, Drive 0" command.
07-Mar 19:29 ol9-sd JobId 25958: 3305 Autochanger "load Volume G03037TA, Slot 37, Drive 0", status is OK.
07-Mar 19:29 ol9-sd JobId 25958: Recycled volume "G03037TA" on Tape device "mhvtl-L80-Autochanger_Dev0" (/dev/tape/by-id/scsi-350223344ab000900-nst), all previous data lost.
07-Mar 19:29 ol9-dir JobId 25958: Max Volume jobs=1 exceeded. Marking Volume "G03037TA" as Used.
07-Mar 19:29 ol9-sd JobId 25958: Elapsed time=00:00:01, Transfer rate=4.715 M Bytes/second
07-Mar 19:29 ol9-sd JobId 25958: Warning: Alert: Volume="G03037TA" alert=1: ERR=The tape drive is having problems reading data. No data has been lost, but there has been a reduction in the performance of the tape. The drive is having severe trouble reading
07-Mar 19:29 ol9-sd JobId 25958: Warning: Alert: Volume="G03037TA" alert=2: ERR=The tape drive is having problems writing data. No data has been lost, but there has been a reduction in the capacity of the tape. The drive is having severe trouble writing
07-Mar 19:29 ol9-sd JobId 25958: Fatal error: Alert: Volume="G03037TA" alert=3: ERR=The operation has stopped because an error has occurred while reading or writing data which the drive cannot correct. The drive had a hard read or write error
07-Mar 19:29 ol9-sd JobId 25958: Fatal error: Alert: Volume="G03037TA" alert=5: ERR=The tape is damaged or the drive is faulty. Call the tape drive supplier helpline.  The drive can no longer read data from the tape
07-Mar 19:29 ol9-sd JobId 25958: Warning: Disabled Volume "G03037TA" due to tape alert=13.
07-Mar 19:29 ol9-sd JobId 25958: Fatal error: Alert: Volume="G03037TA" alert=13: ERR=The operation has failed because the tape in the drive has snapped: Tape snapped/cut in the drive where media can be ejected.
    1. Discard the old tape.
    2. Restart the operation with a different tape.
07-Mar 19:29 ol9-sd JobId 25958: Warning: Disabled Device "mhvtl-L80-Autochanger_Dev0" (/dev/tape/by-id/scsi-350223344ab000900-nst) due to tape alert=20.
07-Mar 19:29 ol9-sd JobId 25958: Warning: Disabled Volume "G03037TA" due to tape alert=20.
07-Mar 19:29 ol9-sd JobId 25958: Fatal error: Alert: Volume="G03037TA" alert=20: ERR=The tape drive needs cleaning: The drive thinks it has a head clog, or needs cleaning.
    1. If the operation has stopped, eject the tape and clean the drive.
    2. If the operation has not stopped, wait for it to finish and then clean the drive.
Check the tape drive users manual for device specific cleaning instructions.
07-Mar 19:29 ol9-sd JobId 25958: Warning: Alert: Volume="G03037TA" alert=21: ERR=The tape drive is due for routine cleaning: The drive is ready for a periodic clean.
    1. Wait for the current operation to finish.
    2. Then use a cleaning cartridge.
Check the tape drive users manual for device specific cleaning instructions.
07-Mar 19:29 ol9-dir JobId 25958: Error: Bacula Enterprise ol9-dir 18.0.1 (28Feb24):
  Build OS:               x86_64-redhat-linux-gnu-bacula-enterprise redhat (Blue
  JobId:                  25958
  Job:                    Linux-Etc-L80-Every4Mins.2024-03-07_19.28.47_35
  Backup Level:           Full
  Client:                 "ol9-bee-fd" 18.0.1 (28Feb24) x86_64-redhat-linux-gnu-bacula-enterprise,redhat,(Blue
  FileSet:                "Linux-Etc" 2022-03-18 11:18:38
  Pool:                   "L80_Full_30Days" (From Job resource)
  Catalog:                "MyCatalog" (From Client resource)
  Storage:                "mhvtl-L80-Autochanger" (From Pool resource)
  Scheduled time:         07-Mar-2024 19:28:47
  Start time:             07-Mar-2024 19:28:50
  End time:               07-Mar-2024 19:29:44
  Elapsed time:           54 secs
  Priority:               10
  FD Files Written:       987
  SD Files Written:       987
  FD Bytes Written:       4,600,366 (4.600 MB)
  SD Bytes Written:       4,715,102 (4.715 MB)
  Rate:                   85.2 KB/s
  Software Compression:   76.9% 4.3:1
  Comm Line Compression:  None
  Snapshot/VSS:           no
  Encryption:             no
  Accurate:               yes
  Volume name(s):         G03037TA
  Volume Session Id:      1
  Volume Session Time:    1709864919
  Last Volume Bytes:      4,838,400 (4.838 MB)
  Non-fatal FD errors:    0
  SD Errors:              1
  FD termination status:  OK
  SD termination status:  Error
  Termination:            *** Backup Error ***
```

Notice that all the same alert codes (1, 2, 3, 513, 20, and 21) are repoted in the Job log by the SD, and in this case, since there are critical drive errors, the job is failed, and the tape drive is disabled.

We can see that the tape drive is indeed disabled with a status storage:
```
* status storage=mhvtl-L80-Autochanger
```

And the (partial) output shows that the drive is indeed (temporarily) disabled, and the Warnings, and Critical TapeAlerts are also listed:
```
[...snip...]
Device Tape is "mhvtl-L80-Autochanger_Dev0" (/dev/tape/by-id/scsi-350223344ab000900-nst) mounted with:
    Volume:      G03037TA
    Pool:        L80_Full_30Days
    Media type:  mhvtl-L80
    Total Bytes=4,838,400 Blocks=74 Bytes/block=65,383
    Positioned at File=1 Block=0
    Device is disabled. User command.                                           <---- Drive has been disabled
    Slot 37 is loaded in drive 0.
    Warning Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Read Warning
    Warning Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Write Warning
    Critical Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Hard Error
    Critical Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Read Failure
    Critical Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Recoverable Snapped Tape
    Critical Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Clean Now
    Warning Alert: at 07-Mar-2024 19:29:44 Volume="G03037TA" alert=Clean Periodic
==
[...snip...]
```

Before going into production, make sure the tape drive is re-enabled. This can be done in one of two ways:
- Restart the Storage Daemon
- Issue the bconsole enable command:
```
* enable storage=mhvtl-L80-Autochanger drive=0
3002 Device ""mhvtl-L80-Autochanger_Dev0" (/dev/tape/by-id/scsi-350223344ab000900-nst)" enabled.
3004 Device ""mhvtl-L80-Autochanger_Dev0" (/dev/tape/by-id/scsi-350223344ab000900-nst)" deleted 1 alert.
```

### Entering Production:

To put this script into production, all that needs to be done after the testing is to remove the `test` command line parameter from the SD's tape drive device(s), restart the Storage Daemon, then monitor your Job log files and the `/opt/bacula/working/bacula-tapealert-py.log` if logging is left enabled.
