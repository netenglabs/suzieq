# Configure SuzieQ
In order to use SuzieQ functionalities, we need to provide a configuration file in [yaml](https://yaml.org/).
A single configuration file can be used to set up all components of SuzieQ, simplyfing the work of the user that
doesn't need to maintain multiple files.

The following example is available at `suzieq/samples/suzieq-cfg.yml` and all fields are described in a table below:

```yaml
data-directory: ./parquet
temp-directory: /tmp/

rest:
  # Uncomment these lines if you're using your own files for the REST server
  # The certificates listed below are provided purely to get started, In any
  # secure deployment, these must be generated specifically for the site and
  # these lines uncommented and containing the location of the site-specific file.
  # rest_certfile: /suzieq/cert.pem
  # rest_keyfile: /suzieq/key.pem
  #
  API_KEY: 496157e6e869ef7f3d6ecb24a6f6d847b224ee4f
  logging-level: WARNING
  address: 127.0.0.1
  port: 8000
  # no-https: True
  # rest-certfile: /secrets/cert.pem
  # rest-keyfile: /secrets/key.pem
  # logfile: /tmp/sq-rest-server.log
  # logsize is in bytes
  # logsize: 10000000
  # log-stdout: True

poller:
  logging-level: WARNING
  period: 60
  connect-timeout: 15
  # logfile: /tmp/sq-poller.log
  # logsize: 10000000
  # log-stdout: True
  # inventory-file: "suzieq/conf/etc/inventory/inventory.yaml"  # Inventory file to use if it is not specified
  # inventory-timeout: 10                                       # The maximum time in seconds for a source to
                                                                # return its node list to the poller
  # update-period: 3600                                         # The update period of the inventory in seconds

  # The manager is the component of the poller producing the final inventory
  # and launching the workers (the components in charge of polling the nodes)
  # Uncomment these lines to customize its behaviour
  #
  # manager:
  #   workers: 1  # Number of workers polling the nodes

  # The chunker is the component of the poller in charge of splitting the
  # final inventory into a number of chunks equal to the number of workers
  # Uncomment these lines to customize its behaviour
  #
  # chunker:
  #   policy: sequential

coalescer:
  # The coalescer has the role to group the single parquet files into a bigger
  # one which represent a snapshot of the entire network, which is performed at
  # every coalescing period. This value can be expressed using the following
  # notation <value><m,h,d,w>, where:
  # m: minutes (i.e. 30m )
  # h: hours (i.e. 12h )
  # d: days (i.e. 1d )
  # w: weeks (i.e. 3w )
  period: 1h
  # Comment the next line if you don't want the archive directory. This dir is
  # purely to save the uncoalesced data in raw format to avoid data loss in case
  # of a bug in the coalescer.
  # archive-directory:
  logging-level: WARNING
  # logfile: /tmp/sq-coalescer.log
  # logsize is specified in bytes
  # logsize: 10000000
  # log-stdout: True

analyzer:
  # By default, the timezone is set to the local timezone. Uncomment
  # this line if you want the analyzer (CLI/GUI/REST) to display the time
  # in a different timezone than the local time. The timestamp stored in
  # the database is always in UTC.
  # Check all the supported values at the "TZ database name" columns of the
  # table at this link: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List
  # timezone: America/Los_Angeles

# ux:             # used for remote CLI
#   engine: rest

```
## Fields description

| Parameter                    | Description                                                                                                   | Default                          | Mandatory           |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |:-------------------------------- | ------------------- |
| data-directory               | directory where data coming from pollers are stored                                                           | -                                | yes                 |
| temp-directory               | change the SuzieQ temp directory                                                                              | /tmp/.suzieq/                    | no                  |
| rest.rest_certfile           | certificate for the REST server                                                                               | -                                | no                  |
| rest.rest_keyfile            | keyfile for the REST server                                                                                   | -                                | no                  |
| rest.API_KEY                 | API key for the REST server                                                                                   | -                                | yes (if using rest) |
| rest.address                 | IP address of the REST server. Used by the CLI and GUI to know the host to contact to receive data.           | 127.0.0.1                        | no                  |
| rest.port                    | port of the REST server                                                                                       | 80                               | no                  |
| rest.logging-level           | logging level for REST server.<br/> Choices: INFO, WARNING, ERROR                                             | WARNING                          | no                  |
| rest.logfile                 | log file for REST                                                                                             | /tmp/sq-rest-server.log          | no                  |
| rest.logsize                 | maximum size of the REST logfile in bytes                                                                     | 10000000                         | no                  |
| rest.log-stdout              | log everything on the standard output instead of a file                                                       | False                            | no                  |
| rest.no-https                | if True, the REST server doesn't use SSL. Highly discouraged in production.                                   | False                            | no                  |
| poller.logging-level         | logging level for the poller.<br/> Choices: INFO, WARNING, ERROR                                              | WARNING                          | no                  |
| poller.logfile               | log file for poller                                                                                           | /tmp/sq-poller.log               | no                  |
| poller.log-stdout            | log on standard output instead of file                                                                        | False                            | no                  |
| poller.period                | how often informations are gathered from each device (in seconds)                                             | 60                               | no                  |
| poller.timeout               | timeout for host connections (in seconds)                                                                     | 15                               | no                  |
| poller.inventory-file        | path of the inventory file. <br/>This value is overridden if the `-i`option is used when starting the poller. | suzieq/config/etc/inventory.yaml | no                  |
| poller.inventory-timeout     | maximum time in seconds for a source to return its nodes                                                      | 10                               | no                  |
| poller.update-period         | inventory update period in seconds.<br/> Only used with dynamic inventories like netbox                       | 3600                             | no                  |
| poller.manager.workers       | number of poller instances to start                                                                           | 1                                | no                  |
| poller.chunker.policy        | defines how the inventory should be splitted between pollers.<br/>Choices:sequential, namespace               | sequential                       | no                  |
| coalescer.period             | the period of data compression<sup>1</sup>                                                                    | 1h                               | no                  |
| coalescer.archived-directory | folder to store archived files in                                                                             | `data-directory`/_archived       | no                  |
| coalescer.logging-level      | coalescer logging level<br/>Choices: INFO, WARNING, ERROR                                                     | WARNING                          | no                  |
| coalescer.logfile            | coalescer log file location                                                                                   | /tmp/sq-coalescer.log            | no                  |
| coalescer.logsize            | max size of the coalescer log file                                                                            | 10000000                         | no                  |
| coalescer.log-stdout         | log on standard output instead of log file                                                                    | False                            | no                  |
| analizer.timezone            | set the timezone                                                                                              | user local timezone              | no                  |
| ux.engine                    | set the engine for the CLI. Set it to 'rest' to use [remote CLI](remote-cli)                                  | -                                | no                  |

!!!Info
    <sup>1</sup>: the coalescer period can be expressed using the format `<value><m,h,d,w>` where: <br>
    m: minutes (i.e. 30m )<br>
    h: hours (i.e. 12h )<br>
    d: days (i.e. 1d )<br>
    w: weeks (i.e. 3w )

## <a name=use-config-file></a>Using the configuration file
The configuration file can be explicitly set as argument of the SuzieQ component (f.e. `sq-poller -c my-config.yml`) or can be placed in one of those locations:

- `./suzieq-cfg.yml` (the same folder where the SuzieQ component is started)
- `$HOME/.suzieq/suzieq-cfg.yml`

!!!Important
    If a SuzieQ config file is placed in both locations specified above, all SuzieQ components will use `./suzieq-cfg.yml` and ignore the other one.
