
#update test data
The test data in tests/data is used by all the tests in tests_sqcmds:test_sqcmds.
It needs to get updated from time to time, especially as we change
data that the poller collects.

to update the test data, go to the root suzieq directory

```bash
export SUZIEQ_POLLER=true; pytest -m update_data -n0 > test_results; unset SUZIEQ_POLLER
```
this will take a long time, on the order of 30 minutes. It has to spin
up vagrant images and collect data and run a little bit of verification.

If the test fails, it means that the data captured isn't complete and should be 
done again. This happens some times, mostly because vagrant doesn't allways
bring up all the devices.

if the test passes, then check to make sure that the updated tests work
```bash
pytest
```

this test will delete the test data from your directory. If this is a git
directory it will git rm the data. It will also update the files in 
tests/integration/samples/sqcmds.


# CNDCN tests


