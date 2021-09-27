# Service File Definition #

A service definition file specifies how to monitor a service and extract state from it. More specifically, a service file definition file is a YAML file that specifies:
  * The name of the service
  * For each type of device to collect service state from:
      * the command to execute to obtain information about the service
      * for each such command, the fields to be extracted
	  * for each field:
    	  * the normalized name of the field
		  * the default value if any, and 
		  * simple arithmetic transformations to be performed to the value of the field to normalize it across devices

The YAML format definition looks as follows, and subsequent sections explain each of these sections :

``` json
service: <name of the service>
period: <periodicity of the poll in seconds> # Optional
type: counters # Optional
ignored-fields: # Optional list of fields to ignore when looking for state changes
  - <field-name-1>
  - <field-name-2>
  ...
keys: # Optional fields which differentiates one record from another
  - <field-name-1>
  - <field-name-2>
  ...
apply:
   <device type or host name>:
      version: <version this applies to or 'all' for all versions>
	  command: <the command to be executed>
	  normalize: <the way to extract fields from a nested JSON output>
	  textfsm: <the textfsm file location to apply over the command output>
	  copy: <the name of the device or hostname from which to copy the commands and fields for this service>
```

## Service Name ##
This is a simple camelCase string that defines the service such as "bgp", "ifCounters". This must be unique.

## Period ##

This is an optional field that defines how frequently must suzieq extract the state of this service. If this field is unspecified, the default is 15 seconds. 

## Type ##
This is an optional field that allows a single value today, "counters", to indicate that the output is potentially different every time the command is run, and to avoid trying to check for changes. This helps suzieq optimize the running of this service

## Ignored Fields ##

The basic idea in monitoring state is to only record changes in service state. In many cases, certain fields change in every state collected. For example, a field such as lastUpTime can be a relative time that changes every time the command is run. Another example is that a protocol may change between multiple inactive states while not in a good state. The observer may only wish to record whether the protocol in a good state or bad state to avoid the uninteresting state transitions when down (think of BGP's Idle, Active and Connect as an example). Suzieq provides two ways to handle this:

* Define a list of fields to ignore in comparing if the state has changed

* Normalize the value to record a single value for a state
	
This is an optional field.

## Keys ##

This is a mandatory field that identifies which set of fields define a record uniquely. For example, in the case of interface counters, the interface name is the key field. The hostname is automatically added as a key field by suzieq. The primary purpose of this field is to simplify queries during the analysis or observation phase.

## Apply ##

This is the workshorse section on the file. It identifies the command to run to obtain the relevant information for this service and how to extract and transform the fields. It contains several subfields. 

## Device Type or Hostname ##

The most common way to breakup the **apply** field is by device type. Device type is identified when suzieq starts up. Examples of device types are linux (for Linux servers), eos (for Arista's OS), cumulus (for Cumulus Linux), nxos (for Cisco's NXOS) and so on. 

Sometimes, a specific device might need to run a special command even though it is of a specific type. An example might be a modified Linux server that provides interface counters differently than via the /proc/net/dev file. In such cases, the device name can be specified instead of the device type. This should be a rare case.

When suzieq is looking for what command to execute for a device to extract state, it first checks to see if there's a section with the hostname, and if that fails, then by device type. If neither of these two options is found for a device, suzieq skips trying to extract any service state from the device.

## Version ##

This specifies if the command and extraction of state is different for different versions of the device or the same. Currently, this field is assumed to be always **all**. Future versions will support the full extent of this field.

## Command ##

This specifies the command to be run to extract state for this service. 

## Command Output Type ##

If the command to extract state produces structured output such as JSON (the only structured output supported for now), the extraction and normalization of the field name is specified via as a list of **xpath-like** fields.

For commands that do not produce structured output, we rely on the textfsm module to convert the unstructured command output to a structured format.

**normalize** is used to define the mapping and transformation of the fields when the output is structuured. 

**textfsm** is used when the output is unstructured. The textfsm field contains the name of the textfsm file to be used for this extraction. The path of the file must be fully specified or its assumed to be in the "config/textfsm" directory.

## Normalizing the Data ##

The normalized field name is to create a single name for a field that is named differently in different device outputs. For example, bytesReceived, rxBytes, bytesRx and inBytes can all be mapped to a common rxBytes field. 

Simple arithmetic operations are used to:

* normalize the value across different devices. For example, a time field defined in seconds in one device output and as milliseconds in another, can be converted to either seconds or milliseconds. 

* unify a field that maybe specified as a single field on one device and as multiple fields in another. For example, if one device provides a single totalLinkTransitions field while another provides totalLinkUps and totalLinkDowns fields, the observer can unify the second output by summing the two fields


To keep the data consistent across outputs, especially if missing, and the value is not a string, the user must specify a default value for the field.

## Field Definition ##

To see how a field normalization works, let's look at a few examples:

## Testing the Normalization ##

## Generating A Schema ##

Suzieq provides a script, `gen_schema.py` which can be used to generate the schema for the state of the service that is extracted. This schema is written out in AVRO format. The schema is used to ensure that the data that is stored is in a consistent format, which simplifies querying later. The schema tries some simple tricks to understand the type of the field, and failing this, it declares the field to be of type "string". The naive rules it uses to determine the type are:

* if the field name ends in "name" or "Name", it must be a string

* if the field name ends in "Cnt" or "Count", it must be an int64

* if the field name ends in "list" or "List", it must be an array

* if the field name ends in "time" or "timestamp", it must be a double

* if the service type is counters, all fields which don't match the above rules are int64

	
The user is encouraged to go fix the types, and add default values, if necessary, after the schema files have been generated. The schema files are stored as .avsc files under a directory called schema under the directory where the service file definitions are present.

The schema generator also uses the **keys** field from the service definition to add a **"key"** attribute as a boolean to those fields.

If the user modifies the schema, and then reruns `gen_schema.py` script, the script preserves the types defined by the user for the field names that are common across the old and the new schema. Fields only in the old schema are assumed to be deleted and thrown away.

## Testing the Schema ##
