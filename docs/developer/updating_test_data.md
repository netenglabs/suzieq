
#update test data
The test data in tests/data is used by all the tests in tests_sqcmds:test_sqcmds.
It needs to get updated from time to time, especially as we change
data that the poller collects.

to update the test data, go to the root suzieq directory

```bash
SUZIEQ_POLLER=true pytest -m update_data -n0
```
this will take a long time, on the order of 30 minutes. It has to spin
up vagrant images and collect data and run a little bit of verification.

If the test fails, it means that the data captured isn't complete and should be 
done again. This happens some times, mostly because vagrant doesn't allways
bring up all the devices.

this test will delete the test data from your directory in tests/data. 
If this is a git
directory it will git rm the data. It will also update the files in 
tests/integration/samples/sqcmds.

if the test passes, then check to make sure that the updated tests work
```bash
pytest
```

Then you should check in the tests/data directories and the tests/integration/sqcmds


# CNDCN tests

These take hours

run the tests
```bash
 SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach" --dist=loadscope -n2
```

if something big has changed and the captured sample *.yml needs to be updated, then 
run :

update the data
```bash
UPDATE_SQCMDS=true SUZIEQ_POLLER=true pytest -m "single_attach or dual_attach" --dist=loadscope -n2
```


# Cleanup
if you run into trouble with vagrant state lying around
```bash
SUZIEQ_POLLER=true pytest -m cleanup -n0
```

