# Updating test data

## updating parsing data

## updating sqcmds when just the output changed, and no data changed

The data that needs to get updated is in `tests/integration/sqcmds/*-samples/`

The way to update these files is use `tests/utilities/update_data.py`

## update test data for sqcmds

The test data in tests/data is used by all the tests in tests_sqcmds:test_sqcmds.
It needs to get updated from time to time, especially as we change data that the poller collects.

To generate only the updated the test data, but not the tests themselves, go to the root suzieq directory and type:

```bash
SUZIEQ_POLLER=data pytest -m update_data -n4
```

This uses the data that has been gathered in the various input directories under ```tests/integration/sqcmds/*-input/``` to produce parquet data to be analyzed.

If you instead use:
```bash
SUZIEQ_POLLER=true pytest -m update_data -n4
```
you can update both the data and the tests (the files under ```tests/integration/sqcmds/*-samples/```.

This both updates the data and is actually a test. When it updates the sqcmds/samples data
it checks to see that the data returned is the same type as before and if not, will fail. In other words, if what was previously
recorded was good output, and this time it returns
and error, exception, or empty ([]) data, than the script will fail.

If the test fails, it might also be because there is a change in the data type trying to be recorded to sqcmds/samples. It's probably best
to run the `utilities/update_sqcmds.py` by hand and see which entry it failed on and why
and then discover if you have found a new bug.

if the test passes, then check to make sure that the updated tests work.

```bash
pytest
```

This test will delete the test data from your directory in `tests/integration/sqcmds/cumulus-input` and `cumulus-samples`.
so you don't have to do anything.
If this is a git
directory it will git rm the data. It will also update the files in 
`tests/integration/samples/sqcmds`.

Then you should check in the `tests/data` directories, and the `tests/integration/sqcmds`

```bash
git add tests/data/sqcmds/cumulus-samples/ tests/data/sqcmds/cumulus-input/
git commit -m 'updated sqcmds test data'
git push
```

## updating NXOS, Junos, or EOS data

We don't have automatic capture of these platforms yet. So you will have to manually
generate the data and run tests. After generating the data, first git rm the previous data. 

However, usually you will not need to update the gathered data, unless we change the commands
that we are running to gather data. If you just need to change the data schema, then you don't need
to worry about this part.

So if it's nxos data,

```bash
git rm -rf tests/data/nxos/parquet-out
mkdir tests/data/nxos
```

copy the generated data to `tests/data/nxos/parquet-out`, or whatever os you are changing

then add it to git

```bash
git add tests/data/nxos/parquet-out
git commmit -m 'latest nxos test data'
git push
```

run pytest

```bash
pytest
```

assuming that all passed

```bash
git add tests/integration/sqcmds/nxos
git commit -m 'latest test sqcmds data for nxos'
git push
```

## gathering input data

if the data that we are collecting changes, then we have to spin up simulations and gathers the data.

```bash
SUZIEQ_POLLER=true pytest -m gather_data -n0
```

You will always want to update the data following the instructions above after you do this.

``` bash
git add tests/data/multidc/parquet-out tests/data/basic_dual_bgp/parquet-out
git commit -m 'udpated cumulus test data'
git push
```

### junos / nxos /eos

We don't have a way to automatically spin up VMs for these and gather the inital data,
so if that needs to be replaced, for instance if a new command is added
then you need to capture gather the data and put it into `tests/integration/sqcmds/nxos-input` and
then do the updating as documented above.

## CNDCN tests

first you must turn all the gathered data into parquet data

```bash
SUZIEQ_POLLER=true pytest -m "update_dual_attach or update_single_attach"
```

Then to run the tests:

```bash
 SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach"
```

### update the data

To update the samples data if any of the data parquet schema has changed:

```bash
UPDATE_SQCMDS=true SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach"
```

you'll need to check in the changes that are made to `tests/integration/all_cndcn/*`

### Gathering the data

This runs each of the 18 CNDCN scenarios in vagrant and gathers the data. It should only be necessary if the commands run are diferent.

These take 2+ hours. I can't get these to run successfully in parallel. It should be possible,
The problems I run into are getting vagrant to reliable destroy and up every single time. Sometimes either vagrant destroy or vagrant up hang and never recover.

```bash
SUZIEQ_POLLER=true pytest -m "gather_single_attach or gather_dual_attach" -n0
```

## Cleanup

if you run into trouble with vagrant state lying around, then run this. This will often be true if any of the updating fails.

```bash
SUZIEQ_POLLER=true pytest -m cleanup -n0 -s
```
