These scripts are used to help with setting up test data.

generate_data.sh is a script which is used to generate
the parquet data directories that we use in our tests in 
tests/data. This is necessary whenever the structure of that data
changes. It is also used to create data from all the scenarios
in cloud-native-data-center-networking. It is run from the
cloud-native-data-center-networking/topologies directory.

update_sqcmds.py is used to update the output for the files in 
tests/integration/sqcmds/samples. If you add a new command 
or a new file to that directory with commands this will update that file
if the output is not filled out. with the -o flag
it will update output that is already filled out.

When using update_sqcmds.py on new data, go through all the errors
and xfails and make sure that they cover known cases. using update_sqcmds
will find exceptions and other errors and you don't want to hide those.


create_test_scafold is used to create those sample yaml files
that need to be updated. This is only used to add a bunch of new tests.
Then you would use udpate_sqcmds.py to fill out the data.