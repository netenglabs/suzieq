# Suzieq testing data generator
This is a guide on how to use the data generator.

With "generators" we define a class which is capable to generate random data and write them on files

## generator directory
This directory contains the SourceGenerator class which must be inherited by all the other generators.

The SourceGenerator class contains only the abstract method `generate` which must be overrided by the inheriting classes. This function is called by the data generator.

## inventorySource directory
This directory contains all the generators which creates an inventory. Right now there is only the one for netbox

## inventorySource/netboxGenerator directory
This directory contains both the NetboxGenerator and the netbox REST server. Both elements are described in the README.md inside the `inventorySource/netboxGenerator` class

## data_generator.py
The goal of this file is to receive a configuration file via the `-c` parameter and run all the generators inside.

An example of configuration is reported and commented below:
``` yaml
seed: 1111                                  # seed used by the faker
generators:
  inventorySource:                          # generator macro-type this field is
                                            # used to define in which directory
                                            # the generator is

    - name: netbox1                         # name which identify a generator
                                            # it must be unique in the same
                                            # macro-type

      type: netboxGenerator                 # generator type
      data:                                 # data to be passed to the generator
                                            # the structure of this field depends
                                            # on the generator type
        
        devices:                            # from now on its only example data
                                            # for a generator
          out_path: "api/dcim/devices"
          out_format: "json"
          count: 10
          name: net1Device
          # ...
```