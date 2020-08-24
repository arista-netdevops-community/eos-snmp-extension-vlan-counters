#!/usr/bin/python -u
# coding: utf-8 -*-

#
# Copyright (c) 2020, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name of Arista Networks nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

"""
This script populates the vlanCounters via a net-snmp extension

Script Information:
-------------------

- Script name: vlanCounters.py
- Version: 0.1
- Date: 08/24/2020

How to use script:
------------------

1. Copy this script to /mnt/flash as vlanCounters.py

2. Copy snmp_passpersist to /mnt/flash
        https://github.com/nagius/snmp_passpersist

3. Enable management api (script uses a unix socket)
        management api http-commands
           protocol unix-socket
           no shutdown

4. Enable Hardware counters for vlan
       hardware counter feature vlan out
       hardware counter feature vlan in

5. Configure SNMP-SERVER extension
       snmp-server extension .1.3.6.1.3.53.9 flash:/vlanCounters.py

6. Re-configure SNMP-SERVER extension when script is updated
       no snmp-server extension .1.3.6.1.3.53.9 flash:/vlanCounters.py
       snmp-server extension .1.3.6.1.3.53.9 flash:/vlanCounters.py
"""

import sys
import snmp_passpersist as snmp
from jsonrpclib import Server

# Configuration section
OID_BASE = ".1.3.6.1.3.53.9"
POLLING_INTERVAL = 30
# Number of SNMP pass_persist update tries
MAX_RETRY = 10

# Only to activate debug mode
# Should not be used in prodcution
DEBUG = False

# Define OID for specific counters
OID_TRANSLATION = dict()
OID_TRANSLATION['inUcastPkts'] = 1
OID_TRANSLATION['outUcastPkts'] = 2
OID_TRANSLATION['inOctets'] = 3
OID_TRANSLATION['outOctets'] = 4
OID_TRANSLATION['inBcastPkts'] = 5
OID_TRANSLATION['outBcastPkts'] = 6
OID_TRANSLATION['inMcastPkts'] = 5
OID_TRANSLATION['outMcastPkts'] = 6

# Define specific OID for description field and values
OID_DESCRIPTION = '.0.'
OID_VALUE = '.1.'


def run_cmd(cmds):
    """
    run_cmd run EOS command using local UNIX socket to eAPI engine

    Run EOS Command using eAPI and local socket. Result is native JSON part of result dictionary

    Parameters
    ----------
    cmds : list
        list of EOS commands to run

    Returns
    -------
    dict
        Full content of the eAPI response
    """
    switch = Server("unix:/var/run/command-api.sock")
    eos_response = switch.runCmds(1, cmds)
    return eos_response


def update():
    """
    update Update SNMP MIB with EOS HW counters for vlans

    Populate SNMP OIDs to store Vlan HW counters from EOS. Data structure in place is:
    {{ OID_BASE }}.{{ VLAN_ID }}.{{ OID_DESCRIPTION | OID_VALUE }}.{{ OID_TRANSLATION[counter] }}

    Examples
    --------
    SNMPv2-SMI::experimental.53.9.0 = STRING: "MIB updated by vlanCounters.py"
    SNMPv2-SMI::experimental.53.9.0.1.0.1 = STRING: "inUcastPkts"
    SNMPv2-SMI::experimental.53.9.0.1.0.2 = STRING: "outUcastPkts"
    SNMPv2-SMI::experimental.53.9.0.1.0.3 = STRING: "inOctets"
    SNMPv2-SMI::experimental.53.9.0.1.0.4 = STRING: "outOctets"
    SNMPv2-SMI::experimental.53.9.0.1.0.5 = STRING: "inBcastPkts"
    SNMPv2-SMI::experimental.53.9.0.1.0.6 = STRING: "outMcastPkts"
    SNMPv2-SMI::experimental.53.9.0.1.1.1 = INTEGER: 77934
    SNMPv2-SMI::experimental.53.9.0.1.1.2 = INTEGER: 0
    SNMPv2-SMI::experimental.53.9.0.1.1.3 = INTEGER: 12207903
    SNMPv2-SMI::experimental.53.9.0.1.1.4 = INTEGER: 0
    SNMPv2-SMI::experimental.53.9.0.1.1.5 = INTEGER: 0
    SNMPv2-SMI::experimental.53.9.0.1.1.6 = INTEGER: 0
    """
    eos_data = run_cmd(cmds=['show vlan counters'])
    pp.add_str('0', "MIB updated by vlanCounters.py")
    for vlan, counters in eos_data[0]['vlanCountersInfo'].items():
        counter_loop = 1
        for counter in counters:
            pp.add_str('0.' + str(vlan) + OID_DESCRIPTION + str(OID_TRANSLATION[counter]),
                       counter)
            pp.add_int('0.' + str(vlan) + OID_VALUE + str(OID_TRANSLATION[counter]),
                       int(counters[counter]),
                       counter)
            counter_loop += 1


if __name__ == '__main__':
    retry_counter = MAX_RETRY
    while retry_counter > 0:
        try:
            pp = snmp.PassPersist(OID_BASE)
            # Activate pass_persist debug
            pp.debug = DEBUG
            # Run SNMP Update process
            pp.start(update, POLLING_INTERVAL)
        except KeyboardInterrupt:
            print 'Exiting on user request'
            sys.exit(1)
        except IOError as e:
            if e.errno == errno.EPIPE:
                print 'snmpd process has closed the pipe'
                sys.exit(1)
            else:
                print 'updater thread has died: ' + str(e)
                sys.exit(1)
        except Exception as e:
            print "main thread has died " + str(e)
        else:
            print 'updater thread has died with no information'
        retry_counter -= 1
    print 'too many retries, exiting to preserve EOS'
