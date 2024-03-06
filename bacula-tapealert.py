#!/usr/bin/env python3

# ----------------------------------------------------------------------------
# - bacula-tapealert.py
# ----------------------------------------------------------------------------
#
# - Bill Arlofski - This script is intended to be a drop-in replacement for
#                   Bacula's original tapealert bash shell script with some
#                   more features.
#
#                 - Initially this script adds the following features:
#                   - Automatically detect, at run time, the correct /dev/sg
#                     node to be called with the tapeinfo utility.
#                   - Logging of actions, debug mode logging, or no logging
#                     at all.
#
# The latest version of this script may be found at: https://github.com/waa
#
# ----------------------------------------------------------------------------
#
# BSD 2-Clause License
#
# Copyright (c) 2024, William A. Arlofski waa@revpol.com
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# 1.  Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2.  Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------

# This example tapeinfo string is used
# when 'test' is True. Edit as needed
# ------------------------------------
fake_tapeinfo_txt = """
Product Type: Tape Drive
Vendor ID: 'STK     '
Product ID: 'T10000B         '
Revision: '0107'
Attached Changer API: No
SerialNumber: 'XYZZY_B1  '
TapeAlert[1]:          Read: Having problems reading (slowing down).
TapeAlert[2]:         Write: Having problems writing (losing capacity).
TapeAlert[3]:    Hard Error: Uncorrectable read/write error.
TapeAlert[13]:  Snapped Tape: The data cartridge contains a broken tape.
TapeAlert[20]:     Clean Now: The tape drive neads cleaning NOW.
TapeAlert[21]: Clean Periodic:The tape drive needs to be cleaned at next opportunity.
MinBlock: 1
MaxBlock: 2097152
SCSI ID: 9
SCSI LUN: 0
Ready: yes
BufferedMode: yes
Medium Type: 0x58
Density Code: 0x58
BlockSize: 0
DataCompEnabled: yes
DataCompCapable: yes
DataDeCompEnabled: yes
CompType: 0xff
DeCompType: 0xff 
"""

# ==================================================
# Nothing below this line should need to be modified
# ==================================================
#
# Import the required modules
# ---------------------------
import os
import re
import sys
import shutil
import subprocess
from docopt import docopt
from datetime import datetime

# Set some variables
# ------------------
progname = 'Bacula TapeAlert'
version = '0.03'
reldate = 'March 05, 2024'
progauthor = 'Bill Arlofski'
authoremail = 'waa@revpol.com'
scriptname = 'bacula-tapealert.py'
prog_info_txt = progname + ' - v' + version + ' - ' + scriptname \
                + ' - By: ' + progauthor + ' ' + authoremail + ' (c) ' + reldate + '\n\n'

# Local system binaries required
# ------------------------------
cmd_lst = ['ls', 'uname', 'lsscsi', 'tapeinfo']

# Define the docopt string
# ------------------------
doc_opt_str = """
Usage:
  bacula-tapealert.py <drive_device> [logging] [-f <logfile>] [test] [debug]
  bacula-tapealert.py -h | --help
  bacula-tapealert.py -v | --version

Options:
  drive_device   The drive's /dev/sg*, /dev/nst#, or /dev/tape/by-id/*-nst, or /dev/tape/by-path/* node.
  test           Run in test mode? Edit the 'fake_tapeinfo_txt' string to suit.
  debug          Log a lot more output, including system utility outputs.
  logging        Should the script log anything at all? Default is False!
 
  -f <logfile>   Where should the script append log file to? [default: /opt/bacula/working/bacula-tapealert-py.log]

  -h, --help     Print this help message.
  -v, --version  Print the script name and version.

"""

# Now for some functions
# ----------------------
def now():
    'Return the current date/time in human readable format.'
    return datetime.today().strftime('%Y%m%d%H%M%S')

def usage():
    'Show the instructions and script information.'
    print(doc_opt_str)
    print(prog_info_txt)
    sys.exit(1)

def log(text, hdr=False, ftr=False):
    'Given some text, write the text to the log_file.'
    if debug or logging:
        with open(log_file, 'a+') as file:
            file.write(('\n' if '[ Starting ' in text else '') \
                        + (now() + ' ' if not ftr else '') + ('- ' if (not hdr and not ftr) else '| ') + text.rstrip('\n') + '\n')

def log_cmd_results(result):
    'Given a subprocess.run() result object, clean up the extra line feeds from stdout and stderr and log them.'
    if debug:
        stdout = result.stdout.rstrip('\n')
        stderr = result.stderr.rstrip('\n')
        if stdout == '':
            stdout = 'N/A'
        if stderr == '':
            stderr = 'N/A'
        log('returncode: ' + str(result.returncode))
        log('stdout: ' + ('\n[begin stdout]\n' + stdout + '\n[end stdout]' if '\n' in stdout else stdout))
        log('stderr: ' + ('\n[begin stderr]\n' + stderr + '\n[end stderr]' if '\n' in stderr else stderr))

def chk_cmd_result(result, cmd):
    'Given a result object, check the returncode, then log and exit if non zero.'
    if debug:
        if result.returncode != 0:
            log('ERROR calling: ' + cmd)
            log(result.stderr.rstrip('\n'))
            sys.exit(result.returncode)

def get_shell_result(cmd):
    'Given a command to run, return the subprocess.run() result.'
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

def cmd_exists(cmd):
    'Check that a binary command exists and is executable.'
    cmd_exists = shutil.which(cmd)
    if debug:
        log('Checking command: ' + cmd)
        log('Command ' + cmd + ' (' + str(cmd_exists) + '): ' + ('OK' if cmd_exists else 'FAIL'))
    return cmd_exists

def get_uname():
    'Get the OS uname to be use in other tests.'
    cmd = 'uname'
    log('Getting OS\'s uname so we can use it for other tests')
    if debug:
        log('shell command: ' + cmd)
    result = get_shell_result(cmd)
    log_cmd_results(result)
    chk_cmd_result(result, cmd)
    return result.stdout.rstrip('\n')

def get_sg_node():
    'Given a drive_device, return the /dev/sg# node.'
    log('Determining the tape drive\'s scsi generic (sg) device node required by tapeinfo')
    if uname == 'Linux':
        # TODO: waa - 20240302 - These lines before the if statement
        # are not necessary. Probably are here for logging mainly.
        # -----------------------------------------------------------
        cmd = 'ls -l ' + drive_device
        if debug:
            log('ls command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        if '/dev/sg' in drive_device:
            # We have been passed an sg device, just return it
            # and skip trying to match it in the lsscsi -g output
            # ---------------------------------------------------
            return drive_device
        elif '/dev/st' in drive_device or '/dev/nst' in drive_device:
            # OK, we caught the simple /dev/st# or /dev/nst# case
            # ---------------------------------------------------
            st = re.sub('.*(/dev/)n(.*)', '\\1\\2', drive_device, re.S)
        elif '/by-id' in drive_device or '/by-path' in drive_device:
            # OK, we caught the /dev/tape/by-id or /dev/tape/by-path case
            # -----------------------------------------------------------
            st = '/dev/' + re.sub('.* -> .*/n*(st\d+).*$', '\\1', result.stdout.rstrip('\n'), re.S)
        cmd = 'lsscsi -g'
        if debug:
            log('lsscsi command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        sg_search = re.search('.*' + st + ' .*(/dev/sg\d+)', result.stdout)
        if sg_search:
            sg = sg_search.group(1)
            log('sg node for drive device: ' + drive_device + ' --> ' + sg)
            return sg
    elif uname == 'FreeBSD':
        sa = re.sub('/dev/(sa\d+)', '\\1', drive_device)
        # On FreeBSD, tape drive device nodes are '/dev/sa#'
        # and their corresponding scsi generic device nodes
        # are '/dev/pass#'. We can correlate them with the
        # 'camcontrol' command.
        # --------------------------------------------------
        # camcontrol devlist
        # <VBOX HARDDISK 1.0>   at scbus0 target 0 lun 0 (pass0,ada0)
        # <VBOX CD-ROM 1.0>     at scbus1 target 0 lun 0 (cd0,pass1)
        # <STK L80 0107>        at scbus2 target 0 lun 0 (ch0,pass2)
        # <STK T10000B 0107>    at scbus3 target 0 lun 0 (pass3,sa0)
        # <STK T10000B 0107>    at scbus4 target 0 lun 0 (pass5,sa2)
        # <STK T10000B 0107>    at scbus5 target 0 lun 0 (pass4,sa1)
        # <STK T10000B 0107>    at scbus6 target 0 lun 0 (pass6,sa3)
        # -----------------------------------------------------------
        cmd = 'camcontrol devlist'
        if debug:
            log('camcontrol command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        sg_search = re.search('.*\((pass\d+),' + sa + '\)', result.stdout)
        if sg_search:
            sg = '/dev/' + sg_search.group(1)
            log('SG node for drive device: ' + drive_device + ' --> ' + sg)
            return sg
    else:
        log('Failed to identify an sg node device for drive device ' + drive_device)
        return 1

def tapealerts(sg):
    'Call tapeinfo and return any tape alerts.'
    cmd = 'tapeinfo -f ' + sg
    if debug:
        log('tapeinfo command: ' + cmd)
    result = get_shell_result(cmd)
    log_cmd_results(result)
    chk_cmd_result(result, cmd)
    return re.findall('TapeAlert\[(\d+)\]: +(.*)', result.stdout)

# ================
# BEGIN THE SCRIPT
# ================
# Assign docopt doc string variable
# ---------------------------------
args = docopt(doc_opt_str, version='\n' + progname + ' - v' + version + '\n' + reldate + '\n')

# Assign the args to variables
# ----------------------------
drive_device = args['<drive_device>']
logging = args['logging']
log_file = args['-f']
test = args['test']
debug = args['debug']

# If the debug or logging variables are
# True, set and create the log directory
# --------------------------------------
if debug or logging:
    date_stamp = now()
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

# Log some startup information to the log file
# --------------------------------------------
log('-'*10 + '[ Starting ' + sys.argv[0] + ' v' + version + ' ]' + '-'*10 , hdr=True)
log('Drive Device: ' + drive_device, hdr=True)

if test:
    log('Testing mode enabled!', hdr=True)
    tapealerts_txt = re.findall('TapeAlert\[(\d+)\]: +(.*)', fake_tapeinfo_txt)
    sg = 'Testing mode enabled: These example results are bogus.'
else:
    # Verify all binaries exist in path and are executable
    # ----------------------------------------------------
    log('Checking that system commands exist: ' + ', '.join(cmd_lst))
    for cmd in cmd_lst:
        bin = cmd_exists(cmd)
        if not bin:
            log('Exiting return code 1')
            sys.exit(1)

    # Get the OS' uname
    # -----------------
    uname = get_uname()

    # Get the /dev/sg# node to check with tapeinfo
    # --------------------------------------------
    sg = get_sg_node()

    # Now call tapealerts() to identify and output any tape alerts
    # ------------------------------------------------------------
    log('Checking for tapeinfo TapeAlerts')
    tapealerts_txt = tapealerts(sg)

# Now, parse and print any TapeAlerts found
# -----------------------------------------
if len(tapealerts_txt) > 0:
    log('WARN: ' + str(len(tapealerts_txt)) + ' TapeAlert' + ('s' if len(tapealerts_txt) > 1 else '') \
        + ' found for drive device ' + drive_device + ' (' + sg + '):')
    for alert in tapealerts_txt:
        # The tape alert text needs to be printed to stdout for the SD to
        # recognize and act on. The 'TapeAlert[xx]:' pre-text is not used
        # by the SD, so it is not printed to stdout.
        #
        # For example, if an actual TapeAlert is:
        # TapeAlert[13]: Snapped Tape: The data cartridge contains a broken tape.
        #
        # The script will just print the following to stdout:
        # Snapped Tape: The data cartridge contains a broken tape.
        # -----------------------------------------------------------------------
        print(alert[1])
        log('      [' + alert[0] + ']: ' + alert[1])
else:
    log('No TapeAlerts found')
log('-'*100, ftr=True)
log(prog_info_txt, ftr=True)
