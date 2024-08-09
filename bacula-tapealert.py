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
#                   - Automatically detect at run time the correct /dev/sg
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
TapeAlert[5]:  Read Failure: Tape faulty or tape drive broken.
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

# Import the required modules
# ---------------------------
import os
import re
import sys
import shutil
import argparse
import subprocess
from datetime import datetime

# Set some variables
# ------------------
progname = 'Bacula TapeAlert'
version = '0.12'
reldate = 'August 08, 2024'
progauthor = 'Bill Arlofski'
authoremail = 'waa@revpol.com'
scriptname = 'bacula-tapealert.py'
prog_info_txt = progname + ' - v' + version + ' - ' + scriptname \
              + ' - By: ' + progauthor + ' ' + authoremail + ' (c) ' + reldate + '\n\n'

# Local system binaries required
# ------------------------------
cmd_lst = ['ls', 'lsscsi', 'tapeinfo', 'uname']

# Set the do_email variable
# -------------------------
do_email = False

# Define the argparse arguments, descriptions, defaults, etc
# waa - Something to look into: https://www.reddit.com/r/Python/comments/11hqsbv/i_am_sick_of_writing_argparse_boilerplate_code_so/
# ---------------------------------------------------------------------------------------------------------------------------------
parser = argparse.ArgumentParser(prog=scriptname, description='Drop-in replacement for tapealert bash/perl script with more features.')
parser.add_argument('-v', '--version', help='Print the script version.', version=scriptname + " v" + version, action='version')
parser.add_argument('-d', '--debug',   help='Log a lot more output, including system utility outputs.', action='store_true')
parser.add_argument('-e', '--email',   help='Send email when TapeAlerts are detected?', default=None)
parser.add_argument('-t', '--test',    help='Run in test mode? Edit the \'fake_tapeinfo_txt\' string in this script to suit.', action='store_true')
parser.add_argument('-l', '--logging', help='Should the script log anything at all? Default is False!', action='store_true')
parser.add_argument('-f', '--file',    help='Where should the script append log file to? [Default: /opt/bacula/log/bacula-tapealert.log]', \
                    default='/opt/bacula/log/bacula-tapealert.log', type=argparse.FileType('a'))
parser.add_argument('-i', '--jobid',   help='The jobid.', default=None)
parser.add_argument('-u', '--smtpuser', help='The SMTP user. [Default: \'\']', default='')
parser.add_argument('-p', '--smtppass', help='The SMTP password. [Default: \'\']', default='')
parser.add_argument('--smtpserver', help='The SMTP server. [Default: localhost]', default='localhost')
parser.add_argument('--smtpport', help='The SMTP port. [Default: 25]', default='25')
parser.add_argument('drive_device', help='The drive\'s /dev/nst#, /dev/tape/by-id/*-nst, or /dev/tape/by-path/* node.')
args = parser.parse_args()

# Now for some functions
# ----------------------
def now():
    'Return the current date/time in human readable format.'
    return datetime.today().strftime('%Y-%m-%d %H:%M:%S')

def log(text, ftr=False):
    'Given some text, write the text to the log_file.'
    if debug or logging:
        with open(log_file, 'a+') as file:
            file.write(('\n' if text.startswith('Starting') else '') \
                        + (now() + ' ' if not ftr else '') + ('jobid: ' + jobid \
                        + ' ' if jobid is not None and not ftr else '') \
                        +  ('- ' if not ftr else '| ') + text.rstrip('\n') + '\n')

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
    if debug and result.returncode != 0:
        log('ERROR calling: ' + cmd)
        log(result.stderr.rstrip('\n'))
    if result.returncode != 0:
        log(result.stderr.rstrip('\n'))
        log('Exiting with return code 0')
        log('-'*(len(prog_info_txt) - 2), ftr=True)
        log(prog_info_txt, ftr=True)
        sys.exit(0)

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
    'Get the systems uname for use in tests.'
    cmd = 'uname'
    log('Getting system\'s uname for use in tests')
    if debug:
        log('shell command: ' + cmd)
    result = get_shell_result(cmd)
    log_cmd_results(result)
    chk_cmd_result(result, cmd)
    return result.stdout.rstrip('\n')

def get_sg_node():
    'Given a drive_device, return the /dev/sg# node.'
    log('Determining the tape drive device\'s sg node required by tapeinfo')
    if uname == 'Linux':
        cmd = 'ls -l ' + drive_device
        if debug:
            log('ls command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        if '/dev/sg' in drive_device:
            # A /dev/sg device was passed to the script, so
            # issue a warning, skip trying to match it in the
            # lsscsi -g output, and just return the /dev/sg node
            # --------------------------------------------------
            log('NOTE: A /dev/sg node was passed to this script')
            log('      Be aware that this may not be the correct sg node for the drive being tested')
            log('      It is recommended to pass this script the same node set for the \'ArchiveDevice\'')
            return drive_device
        elif any(x in drive_device for x in ('/dev/st', '/dev/nst')):
            # A /dev/st# or /dev/nst# case was caught
            # ---------------------------------------
            st = re.sub('.*(/dev/)n(.*)', '\\1\\2', drive_device, re.S)
        elif any(x in drive_device for x in ('/by-id', '/by-path')):
            # A /dev/tape/by-id or /dev/tape/by-path case was caught
            # ------------------------------------------------------
            st = '/dev/' + re.sub('.* -> .*/n*(st\\d+).*$', '\\1', result.stdout.rstrip('\n'), re.S)
        cmd = 'lsscsi -g'
        if debug:
            log('lsscsi command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        sg_search = re.search('.*' + st + ' .*(/dev/sg\\d+)', result.stdout)
        if sg_search:
            sg = sg_search.group(1)
            log('sg node determined for drive device: ' + sg)
            return sg
    elif uname == 'FreeBSD':
        sa = re.sub(r'/dev/(sa\d+)', '\\1', drive_device)
        cmd = 'camcontrol devlist'
        if debug:
            log('camcontrol command: ' + cmd)
        result = get_shell_result(cmd)
        log_cmd_results(result)
        chk_cmd_result(result, cmd)
        sg_search = re.search('.*\\((pass\\d+),' + sa + '\\)', result.stdout)
        if sg_search:
            sg = '/dev/' + sg_search.group(1)
            log('SG node for drive device: ' + drive_device + ' --> ' + sg)
            return sg
    else:
        log('Failed to identify an sg node device for drive device ' + drive_device)
        log('Exiting with return code 0')
        sys.exit(0)

def tapealerts(sg):
    'Call tapeinfo and return any tape alerts.'
    cmd = 'tapeinfo -f ' + sg
    if debug:
        log('tapeinfo command: ' + cmd)
    result = get_shell_result(cmd)
    log_cmd_results(result)
    chk_cmd_result(result, cmd)
    return re.findall(r'(TapeAlert\[\d+\]): +(.*)', result.stdout)

def send_email():
    'Send the email.'
    # Thank you to Aleksandr Varnin for this short and simple to implement solution
    # https://blog.mailtrap.io/sending-emails-in-python-tutorial-with-code-examples
    # -----------------------------------------------------------------------------
    # f-strings require Python version 3.6 or above
    message = f'''Content-Type: text/plain\nMIME-Version: 1.0\nTo: {email}\nFrom: {fromemail}\nSubject: {subject}\n\n{msg}'''
    try:
        with smtplib.SMTP(smtpserver, smtpport) as server:
            if smtpuser != '' and smtppass != '':
                server.login(smtpuser, smtppass)
            server.sendmail(fromemail, email, message)
            log('Successfully emailed TapeAlerts to: ' + email)
    except (gaierror, ConnectionRefusedError):
        log('Failed to connect to the SMTP server. Bad connection settings?')
        sys.exit(0)
    except smtplib.SMTPServerDisconnected:
        log('Failed to connect to the SMTP server. Wrong user/password?')
        sys.exit(0)
    except smtplib.SMTPException as err:
        log('Error occurred while communicating with SMTP server ' + smtpserver + ':' + str(smtpport))
        log('  Error was: ' + str(err))
        sys.exit(0)

# ================
# BEGIN THE SCRIPT
# ================
# Assign the args to variables
# ----------------------------
test = args.test
debug = args.debug
jobid = args.jobid
logging = args.logging
log_file = args.file.name
email = fromemail = args.email
drive_device = args.drive_device
smtpuser = args.smtpuser
smtppass = args.smtppass
smtpport = args.smtpport
smtpserver = args.smtpserver

# If the debug or logging variables are
# True, set and create the log directory
# if it does not exist
# --------------------------------------
if debug or logging:
    date_stamp = now()
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

# Log some startup information
# ----------------------------
log('Starting ' + progname + ' v' + version)
log('Drive Device: ' + drive_device)

# Do minor email validation and set the do_email
# variable to True if we have what looks like an email
# ----------------------------------------------------
if email != None and '@' not in email:
    log('email address \'' + email + '\' does not look like a valid email, will not attempt to send')
elif email != None:
    log('email is set to \'' + email + '\', will attempt to send')
    do_email = True

if test:
    log('The \'test\' variable is True. Testing mode enabled!')
    tapealerts_txt = re.findall(r'(TapeAlert\[\d+\]): +(.*)', fake_tapeinfo_txt)
    sg = 'These test mode results are bogus'
else:
    # Verify all binaries exist in path and are executable
    # ----------------------------------------------------
    log('Checking that system utilities exist: ' + ', '.join(cmd_lst))
    for cmd in cmd_lst:
        bin = cmd_exists(cmd)
        if not bin:
            log('Exiting with return code 0')
            sys.exit(0)

    # Get the OS uname
    # ----------------
    uname = get_uname()

    # Get the /dev/sg# node to check with tapeinfo
    # --------------------------------------------
    sg = get_sg_node()

    # Call tapealerts() to identify any TapeAlerts
    # and set the tapealerts_txt text variable
    # --------------------------------------------
    log('Calling tapeinfo to check drive for TapeAlerts')
    tapealerts_txt = tapealerts(sg)

# Parse and print any TapeAlerts found
# ------------------------------------
if len(tapealerts_txt) > 0:
    msg = ''
    warn_txt = '(' + str(len(tapealerts_txt)) + ') TapeAlert' + ('s' if len(tapealerts_txt) > 1 else '')
    log('WARN: ' + warn_txt + ' detected on drive device:')
    for alert in tapealerts_txt:
        # The TapeAlert line(s) need to be printed to stdout for the SD to
        # recognize and act on.
        #
        # The SD code is *only* looking for 'TapeAlert[%d]' and ignores
        # everything after the ':' (colon), so we print just this part of
        # any TapeAlert lines to stdout.
        #
        # For example, if an actual TapeAlert line is:
        # TapeAlert[13]: Snapped Tape: The data cartridge contains a broken tape.
        #
        # The script will just print the following to stdout:
        # TapeAlert[13]
        #
        # If logging is enabled, the script will log the TapeAlert code and the
        # rest of the TapeAlert line:
        # [13]: Snapped Tape: The data cartridge contains a broken tape.
        # -----------------------------------------------------------------------
        print(alert[0])
        log('      ' + alert[0].replace('TapeAlert', '') + ': ' + alert[1])
        msg += alert[0] + ': ' + alert[1] + '\n'
    if do_email:
        import smtplib
        from socket import gaierror
        subject = progname + ' - WARN: ' + warn_txt + ' detected ' + ('during jobid: ' + jobid  + ' ' if jobid != None else '') + 'on device \'' + drive_device + '\''
        msg_hdr = 'The following ' + warn_txt + (' were' if len(tapealerts_txt) > 1 else ' was') + ' detected:\n'
        msg = msg_hdr + '-'*(len(msg_hdr) - 1) + '\n' + msg + '\n' + '-'*(len(prog_info_txt) - 2) + '\n' + prog_info_txt
        send_email()
else:
    log('No TapeAlerts found')
log('-'*(len(prog_info_txt) - 2), ftr=True)
log(prog_info_txt, ftr=True)
