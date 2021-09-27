# Testing in Suzieq

Suzieq has to be well tested, and it has to be tested automatically: We don't have testers, it's just us. We've tried to be comprehensive and representative in our automatic tests, but we can always do better.

to test,

```bash
pytest
```

## sqcmds

Most of our testing is done by running through each of our commands and comparing against previous output. This is pretty good, testing the whole read, analysis, and cli pipeline.

When you run pytest, it uses captured parquet data and then runs the cli against that data and check the output against previously stored output data.

The way that this works is that Suzeiq has a different set of tests that capture the output from devices, and store that. Then parquet data is created, then the CLI is run against that and output data is produced. How to do that is documented in [updating_test_data.md](updating_test_data.md)

## Testing per NOS

Because we rely on playback of commands and because each NOS brings it's own fun in parsing output, we do require new tests for each new NOS. What we need is the `--run-once=gather` data that is in `tests/integration/sqcmds/*-input` and we will need to update the data over time as we add new commands or change how exactly we process data. What this means is that we need to have some set topology (usually simulated in vagrant), that we can reliably gather the same data from every time. From that we then generate parquet data. From the parquet data we generate sample output that is then compared going forward. For cumulus, Suzieq can automatically spin up the VMs, generate the run-once=gather data, generate the parquet data, and generate the sample data to compare, and then we can run the tests as usual.

When adding a new NOS, we have a generic set of commands we want to run through in the sample data, which can be created by the utility script `tests/utilities/create_test_scafold.py`.

| NOS | Owners| Topology | spin up VM in pytest| autogenerate in pytest |
| --- | ------| ----| ---- | --- |
| Cumulus | ddutt@stardustsystems.net, justin@stardustsystems.net | https://github.com/netenglabs/cloud-native-data-center-networking  (test_update_data has which simulations are used)| Yes | Yes |
| Junos QFX | ddutt@stardustsystems.net, justin@stardustsystems.net | https://github.com/Juniper/vqfx10k-vagrant (full-2qfx-4srv-evpnvxlan) | No | Yes|
| Junos MX | ddutt@stardustsystems.net, justin@stardustsystems.net | | No | No |
| EOS | ddutt@stardustsystems.net, justin@stardustsystems.net | | No | Yes |
| NXOS | ddutt@stardustsystems.net, justin@stardustsystems.net | | No | Yes |
| SONIC | ??? | | No | Yes |

## Testing the poller code

As mentioned above, our regular tests focus on running through all the commands on the client, which does not directly test the poller. So the testing we have for the poller is in the automatic generation of test data. This is actually pretty effective, but doesn't catch everything. For instance, it's based on polling one with run-once=gather, and so it doesn't catch things like when polled devices reboot.

## Unit testing

Suzieq doesn't have much unit testing. Please help us figure out how to do that in a way that makes sense.

## Where we need help

Every code checking should have some kind of test with it.

Where we really need help is improving our testing. Suzieq testing relies on running sqcmds end-to-end and comparing output. However, it has some downsides. First, it's kind of fragile and it requires that for every NOS that we support we have to somebody to have ready access all the time so that we can update test data. In other words, if we change a service and decide it needs more data, we can't support that for a NOS that somebody can't get output for. Also, when we make changes to things like services we have to regenerate the test `./updating_test_data.md`. The second issue is that we can't test all possible interactions, so there are things we miss. Third, we aren't testing the full poller - client interaction. We rely on using run-one=gather, but if there are problems in the way that the poller works overtime, we'll miss that. fourth, as we move to a long running process for read time (like a REST server), how do we replay the data through the service?
