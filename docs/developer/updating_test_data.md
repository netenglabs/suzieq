
# update test data for sqcmds
The test data in tests/data is used by all the tests in tests_sqcmds:test_sqcmds.
It needs to get updated from time to time, especially as we change
data that the poller collects. 

to generate the updated the test data, go to the root suzieq directory

```bash
SUZIEQ_POLLER=true pytest -m update_data -n0
```
This uses the data that has been gathered to produce parquet data to be analyzed.


This both updates the data and is actually a test. When it updates the sqcmds/samples data
it checks to see that the data returned is the same type as before and if not, will fail. In other words, if what was previously
recorded was good output, and this time it returns
and error, exception, or empty ([]) data, than the script will fail.

 
If the test fails, it might also be because there is a change in the data type trying to be recorded to sqcmds/samples. It's probably best
to run the utilities/update_sqcmds.py by hand and see which entry it failed on and why
and then discover if you have found a new bug.


if the test passes, then check to make sure that the updated tests work.
```bash
pytest
```

This test will delete the test data from your directory in tests/integration/sqcmds/cumulus-input and cumulus-samples. 
so you don't have to do anything.
If this is a git
directory it will git rm the data. It will also update the files in 
tests/integration/samples/sqcmds.

Then you should check in the tests/data directories and the tests/integration/sqcmds

```bash
git add tests/data/sqcmds/cumulus-samples/ tests/data/sqcmds/cumulus-input/
git commit -m 'updated sqcmds test data'
git push
```

# updating NXOS, Junos, or EOS data
We don't have automatic capture of these platforms yet. So you will have to manually
generate the data and run tests. After generating the data, first git rm the previous data.

So if it's nxos data,
```bash
git rm -rf tests/data/nxos/parquet-out
mkdir tests/data/nxos
```
copy the generated data to tests/data/nxos/parquet-out

then add it to git
```bash
git add tests/data/nxos/parquet-out
git commmit -m 'latest nxos test data'
git push
```

to update the sqmds
```bash
for file in tests/integration/sqcmds/nxos/*.yml; do echo $file; python3 tests/utilities/update_sqcmds.py -f $file -o; done
```
make sure that none of them fails. Just as above, if the data type returned is different
update_sqcmds.py will fail.

run pytest
```bash
pytest
```
assuming that all passed

```bash
git add tests/integration/sqcmds/nxos
git commit -m 'latest test sqcmds data  for nxos'
git push
```

# gathering input data
if the data that we are collecting changes, then we have to spin up simulations and gathers the data.

```bash
SUZIEQ_POLLER=true pytest -m gather_data -n0
```

You will always want to update the data following the instructions above after you do this.


```
git add tests/data/multidc/parquet-out tests/data/basic_dual_bgp/parquet-out 
git commit -m 'udpated cumulus test data'
git push
```

# CNDCN tests

These take hours

I can't get these to run successfully in parallel. It should be possible, I've done it with a bash
script, but I can't get it to work correctly with pytest.

run the tests
```bash
 SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach" -n0 
```

if you want to try parallel
```bash
 SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach" -n2 --dist=loadscope
```

if something big has changed and the captured sample *.yml needs to be updated, then 
run :

update the data
```bash
UPDATE_SQCMDS=true SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach" -n0
```
you'll need to check in the changes that are made to tests/integration/all_cndcn/*


# Cleanup
if you run into trouble with vagrant state lying around, then run this. This will often be true if any of the updating fails. 
```bash
SUZIEQ_POLLER=true pytest -m cleanup -n0 -s
```

