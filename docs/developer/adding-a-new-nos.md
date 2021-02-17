# Adding a New NOS to Suzieq

Multi-vendor support is integral to how Suzieq is designed. If you're a developer trying to add a new NOS, here are the key steps that you need to accomplish:

- Does the device have SSH, and or REST, support. Suzieq only supports these two methods, but relies on SSH access to automatically identify the NOS, unless you can supply the NOS identifier in the inventory output.
- Decide the name you intend to use for your NOS. Picking a name that fits with what is popular is better (eos rather than arista-eos, for example). If there can be more than one major variation between the command outputs on different platforms (JunOS is a classic example), then you'll need to pick a name that's more precise (junos-qfx and junos-mx, for example).
- For every file in suzieq/config/*.yml, look up the command that'll provide the equivalent information for that table.
- Figure out a method that you can identify the NOS with. The most common command is "show version" that works across many NOS.
- Add a NOS-specific class object in suzieq/poller/nodes/node.py.

Lets dig in to each piece now. We'll start with a different order than the one listed above. The order of the list above helps you plan the work before you begin. The work itself needs to be done in a different order to make incremental progress.

## Identifying the NOS

Suzieq can identify the NOS automatically if it can access the device via SSH. Every device's REST API differs from every other NOS' REST API, and worse, can change. For this reason, if you wish to use only REST access for a NOS, the inventory file MUST identify the NOS. Arista's EOS follows this model. NXOS, Junos and Cumulus all use SSH to poll the device.

### Automatic Identification of NOS

This is not a mandatory step, but this method enables easier inventory specification if provided.gi

Find the command, via SSH, that can be used to identify the NOS type. Specifically, Suzieq needs to identify the following pieces of info for a node:

- The device's unique NOS name
- The device's model, if the NOS name is not unique across models, such as JunOS or IOS.

The most common command to identify a NOS is `show version`. Here is the sample command output from NXOS.
```
leaf1# show version
Cisco Nexus Operating System (NX-OS) Software
TAC support: http://www.cisco.com/tac
Documents: http://www.cisco.com/en/US/products/ps9372/tsd_products_support_series_home.html
Copyright (c) 2002-2020, Cisco Systems, Inc. All rights reserved.
The copyrights to certain works contained herein are owned by
other third parties and are used and distributed under license.
Some parts of this software are covered under the GNU Public
License. A copy of the license is available at
http://www.gnu.org/licenses/gpl.html.

Nexus 9000v is a demo version of the Nexus Operating System

Software
  BIOS: version 
 NXOS: version 9.3(4)                                 <--- NXOS and version identification
  BIOS compile time:  
  NXOS image file is: bootflash:///nxos.9.3.4.bin
  NXOS compile time:  4/28/2020 21:00:00 [04/29/2020 06:28:31]


Hardware
  cisco Nexus9000 C9300v Chassis                     <--- NXOS Model Identification
  Intel Core Processor (Skylake, IBRS) with 6096736 kB of memory.
  Processor Board ID 9R62LBVFU3T

  Device name: leaf1                                 
  bootflash:    4287040 kB
Kernel uptime is 2 day(s), 7 hour(s), 11 minute(s), 10 second(s) <--- Uptime Identification

Last reset
  Reason: Unknown
  System version:
  Service:

plugin
  Core Plugin, Ethernet Plugin

Active Package(s):
        
leaf1#
```

In the output above, the markings show the specific places where the key pieces of information resides (i) the NOS name, (ii) the NOS model and (iii) the device uptime.

If the command is something other than `show version` or `hostnamectl`, you'll need to add the command to the list passed in the routine `get_device_type_hostname` in the file suzieq/poller/nodes/node.py.

Hostnames can be tricky. NXOS provides the non-FQDN output in `show version`, but uses the FQDN version in other command outputs (such as LLDP). For this reason, its important to ensure that you use the right command to extract the hostname. If the NOS you're adding uses `show hostname`, then there's no new command to add. Otherwise, add the command to extract the hostname also to the list in the routine `get_device_type_hostname`.

Once the output is extracted, you need to handle the parsing and specification of it. This is done in the routine `_parse_device_type_hostname`, also in the same file, suzieq/poller/nodes/node.py. Look at the code in that routine to add support for determining the NOS type and the hostname.

### Adding a NOS-Specific Class

Since each NOS has its own command and output for parsing boot up time, retrieving the version of the NOS etc, you'll need to create a new NOS-specific class in the file suzieq/poller/nodes/node.py. Look at either the NxosNode class or JunosNode class to see how to add a new NOS type and what the additional routines to support are. Typically, you'll need to add two routines, `init_boot_time` and `_parse_device_type_hostname` routines to this Node class as the commands and outputs to get this information is specific to each NOS.  

If you're using the REST API to access the information from this NOS, you will need to add another routine, `rest_gather` to this new NOS Node class. Look at EosNode's `rest_gather` method in the file to get the template for creating this class. In general, there's a little more work to do if you're using the REST API. This maybe a limitation of the current implementation in Suzieq rather than a reflection of REST support.

### Authentication Methods Supported

At the time of this writing, Suzieq supports the following authentication methods:
- Username/password
- Private key files (recommended)
- Private Key files with passphrase (recommended)
- Use SSH Config file for more complex cases

Suzieq MUST NEVER access any update command. The only commands it cares about are read commands. For this reason, its critical to assign a username for Suzieq that has only read permission.

## Adding the Commands to Gather Information

Once you've created this information, you're now ready to gather inputs.

For every file in config/*.yml in the Suzieq tree, determine the command that provides the information relevant to the table for the NOS you're adding support. For example, BGP information is extracted from the file config/bgp.yml. For Cumulus, the command to extract the relevant BGP information is "net show bgp vrf all neighbor json", and is visible under the cumulus NOS key in that file. Some of the tables need more than one command to gather the output at times (see NXOS' bgp command set in the same file).

Pick a command output that is structured, specifically JSON. Unstructured output is acceptable, but you'll need to know how to write textfsm parsers for those commands. Choose a command that provides all the info over one that is structured, but incomplete. If multiple commands are used, its fine to have mix commands that provide structured output with commands that don't. Textfsm parsers MUST be present in the config/textfsm_templates directory.

For each command, you'll need to advice Suzieq as to how to extract the relevant data. If this is too complicated for you to identify, just adding the command name, you can do something to help the Suzieq developers perform this task for you. Just add the command and leave out the normalize or textfsm key specification. Then, run the poller with the options --run-once=gather --output-dir=<outputdir>. This will create a set of ".output" files in the directory specified. The directory is created if not present. However, the outputs are appended to an existing file if present. For example, the lldp output is appended to the lldp.output file if such a file is present. Therefore, if you're debugging the command and the code, its important to remove all .output files from that directory before running the poller after the very first time. However, as we discuss in the subsequent paragraph, this step is not always required.

Tar this directory and supply it to one of the developers, Dinesh or Justin, at this time, and they can now do the remaining work to add support for extracting the data for the NOS you're adding support for. The more varied the output that is gathered, the better will be the support the developers can provide. For example, if you only provide good outputs, the developers may not be able to anticipate what needs to be done when the output is bad. You can gather the output several times by changing the condition on the devices and running the poller with --run-once=gather multiple times. The outputs can all be sent to the same directory or each can be put in a different directory, and all this input can be provided to the developers.

## Massaging the Output Gathered

All data stored by Suzieq is structured and has a schema. This schema is stored in config/schema. In many cases, it is not possible for the command output to fit into the schema directly. In such cases, its required to massage the output to fit the schema. Each file in config/*.yml has a corresponding python file under suzieq/poller/services/ directory that contains the code to massage the output. For example, suzieq/poller/services/bgp.py contains code that massages the output for the BGP commands from different NOS. Look at an existing file to determine how to add support for your NOS.

## Adding the NOS to the List of Known NOS

In the file suzieq/utils.py is a routine called known_devtypes(). Please add the new NOS name to this list.

## Debugging the Setup

It is recommended that you first check that the NOS can be recognized, if you're using automatic NOS detection method (available with SSH access only). You can point the poller with an inventory file that contains a single device and test the connectivity and command access via the use of a single service, such as lldp or device. Look at the output of /tmp/sq-poller.log for the results of the connection to the device. Any errors will be reported there. 

You can debug the SSH or HTTP process by setting the log level to DEBUG or INFO in the default suzieq config file, stored at ~/.suzieq/suzieq-cfg.yml. An example of the contents of this file is:

```
data-directory: /home/netenglabs/work/suzieq/tests/data/multidc/parquet-out
service-directory: /home/netenglabs/work/suzieq/config
schema-directory: /home/netenglabs/work/suzieq/config/schema
temp-directory: /tmp/suzieq
# kafka-servers: localhost:9093
logging-level: WARNING
```

Change the last line that has WARNING in it to INFO or DEBUG to troubleshoot any issues. The log file, /tmp/sq-poller.log contains the relevant output.

## Testing

We have to have tests for any new code, especially to support a new NOS. At a minimum we need to have a reliable topology that we can then use to reliably generate run-once=gather output so that we can run through all the necessary tests. See our [testing doc](testing.md). So as part of the PR submitted, its essential that we get the data we need to run our tests. Primairly, we want:
- The data gathered by running the poller with the --run-once=gather. The output directory (sqpoller-output, by default) can be run through an anonymizer to anonymize the output. The anonymizer anonymizes the hostname, IP address and MAC address at this time. The anonymizer is beta code, and we don't guarantee that everything is anonymized. Please verify that it is. Provide us the sqpoller-directory with the *_anon.utput files.
- This data can be added to the tests/integration/sqcmds directory with the name <nos>-input, just like nxos-input, eos-input etc.
- Write the equivalent tests in the <nos>-samples directory. You can copy the existing files from cumulus-samples directory, and then run ```python suzieq/tests/utilities/update_sqcmds.py -o -f <each file in the samples fir>```.
- Update the tags to add your NOS name to the list.
- Run pytests to make sure that all tests pass with this data.
