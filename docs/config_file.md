# Configure SuzieQ

In order to use SuzieQ functionalities, we need to provide a configuration file.
A single [yaml](https://yaml.org/) configuration file can be used to set up all components of SuzieQ, simplyfing the work of the user that
doesn't need to maintain multiple files.

By default SuzieQ looks for the configuration file in one of these locations in the following order:

- `./suzieq-cfg.yml` (the same folder where the SuzieQ component is started)
- `$HOME/.suzieq/suzieq-cfg.yml`

The configuration file can be explicitly set as argument of any of the SuzieQ components using `-c` flag

```shell
sq-poller -c my-config.yml
```

A complete SuzieQ configuration file example is available [here](https://github.com/netenglabs/suzieq/blob/master/suzieq/config/etc/suzieq-cfg.yml) and all fields are described in a table below.

The following snipped is an example of configuration file.

```yaml
data-directory: ./parquet
temp-directory: /tmp/

rest:
  API_KEY: 496157e6e869ef7f3d6ecb24a6f6d847b224ee4f
  logging-level: WARNING
  address: 127.0.0.1
  port: 8000

poller:
  logging-level: WARNING
  period: 60
  connect-timeout: 15

coalescer:
  period: 1h
  logging-level: WARNING
```

## Fields description

| Parameter                    | Description                                                                                                                                                                                                                          | Default                          | Mandatory           |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |:-------------------------------- | ------------------- |
| data-directory               | The directory where the poller stores the data collected from the network                                                                                                                                                            | -                                | yes                 |
| temp-directory               | Where SuzieQ stores temporary data                                                                                                                                                                                                   | /tmp/.suzieq/                    | no                  |
| rest.rest_certfile           | certificate for the REST server                                                                                                                                                                                                      | -                                | no                  |
| rest.rest_keyfile            | keyfile for the REST server                                                                                                                                                                                                          | -                                | no                  |
| rest.API_KEY                 | API key for the REST server                                                                                                                                                                                                          | -                                | yes (if using rest) |
| rest.address                 | IP address of the REST server.                                                                                                                                                                                                       | 127.0.0.1                        | no                  |
| rest.port                    | port of the REST server                                                                                                                                                                                                              | 80                               | no                  |
| rest.logging-level           | logging level for REST server.<br/> Choices: INFO, WARNING, ERROR                                                                                                                                                                    | WARNING                          | no                  |
| rest.logfile                 | log file for REST                                                                                                                                                                                                                    | /tmp/sq-rest-server.log          | no                  |
| rest.logsize                 | maximum size of the REST logfile in bytes                                                                                                                                                                                            | 10000000                         | no                  |
| rest.log-stdout              | log everything on the standard output instead of a file                                                                                                                                                                              | False                            | no                  |
| rest.no-https                | if True, the REST server doesn't use SSL. Highly discouraged in production.                                                                                                                                                          | False                            | no                  |
| poller.logging-level         | logging level for the poller.<br/> Choices: INFO, WARNING, ERROR                                                                                                                                                                     | WARNING                          | no                  |
| poller.logfile               | log file for poller                                                                                                                                                                                                                  | /tmp/sq-poller.log               | no                  |
| poller.log-stdout            | log on standard output instead of file                                                                                                                                                                                               | False                            | no                  |
| poller.period                | how often informations are gathered from each device (in seconds)                                                                                                                                                                    | 60                               | no                  |
| poller.timeout               | timeout for host connections (in seconds)                                                                                                                                                                                            | 15                               | no                  |
| poller.inventory-file        | path of the inventory file. <br/>When the inventory file is provided with the `-I` option to the poller, this field is ignored                                                                                                       | suzieq/config/etc/inventory.yaml | no                  |
| poller.inventory-timeout     | maximum time in seconds for a source to return its nodes                                                                                                                                                                             | 10                               | no                  |
| poller.update-period         | inventory update period in seconds.<br/> Only used with dynamic inventories like netbox                                                                                                                                              | 3600                             | no                  |
| poller.manager.workers       | number of poller instances to start<br/>When the number of workers is provided with the -w option to the poller, this field is ignored                                                                                               | 1                                | no                  |
| poller.chunker.policy        | defines how the inventory should be splitted between pollers.<br/>Choices:sequential, namespace                                                                                                                                      | sequential                       | no                  |
| coalescer.period             | the period of data compression<sup>1</sup>                                                                                                                                                                                           | 1h                               | no                  |
| coalescer.archived-directory | folder to store archived files in                                                                                                                                                                                                    | `data-directory`/_archived       | no                  |
| coalescer.logging-level      | coalescer logging level<br/>Choices: INFO, WARNING, ERROR                                                                                                                                                                            | WARNING                          | no                  |
| coalescer.logfile            | coalescer log file location                                                                                                                                                                                                          | /tmp/sq-coalescer.log            | no                  |
| coalescer.logsize            | max size of the coalescer log file                                                                                                                                                                                                   | 10000000                         | no                  |
| coalescer.log-stdout         | log on standard output instead of log file                                                                                                                                                                                           | False                            | no                  |
| analizer.timezone            | By default, the timezone is set to the local timezone.<br>Set this value if you want to display the time in a different timezone.<br>Check [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List) the available values. | user local timezone              | no                  |
| ux.engine                    | set the engine for the CLI. Set it to 'rest' to use [remote CLI](./remote-cli.md)                                                                                                                                                         | -                                | no                  |

!!!Info
    <sup>1</sup>: the coalescer period can be expressed using the format `<value><m,h,d,w>` where: <br>
    m: minutes (i.e. 30m )<br>
    h: hours (i.e. 12h )<br>
    d: days (i.e. 1d )<br>
    w: weeks (i.e. 3w )
