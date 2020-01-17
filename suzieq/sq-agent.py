import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path
import uvloop

from confluent_kafka import Producer

import daemon
from daemon import pidfile

from node import init_hosts
from suzieq.service import init_services
from suzieq.writer import init_output_workers, run_output_worker

PID_FILE = "/tmp/suzieq.pid"


def validate_parquet_args(userargs, output_args):
    """Validate user arguments for parquet output"""

    if not userargs.output_dir:
        output_dir = "/tmp/parquet-out/suzieq"
        logging.warning(
            "No output directory for parquet specified, using"
            "/tmp/suzieq/parquet-out"
        )
    else:
        output_dir = userargs.output_dir

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.isdir(output_dir):
        logging.error("Output directory {} is not a directory".format(
            output_dir))
        print("Output directory {} is not a directory".format(
            output_dir))
        sys.exit(1)

    logging.info("Parquet outputs will be under {}".format(output_dir))
    output_args.update({"output_dir": output_dir})

    return


def validate_kafka_args(userargs, output_args):
    """ Validate user arguments for kafka output"""

    if not userargs.kafka_servers:
        logging.warning("No kafka servers specified. Assuming localhost:9092")
        servers = "localhost:9092"
    else:
        servers = userargs.kafka_servers

    try:
        _ = Producer({"bootstrap.servers": servers})
    except Exception as e:
        logging.error("ERROR: Unable to connect to Kafka servers:{}, e",
                      servers, e)
        print("ERROR: Unable to connect to Kafka servers:{}, e",
              servers, e)
        sys.exit(1)

    output_args.update({"bootstrap.servers": servers})

    return


def _main(userargs):

    uvloop.install()

    if not os.path.exists(userargs.service_dir):
        logging.error(
            "Service directory {} is not a directory".format(
                userargs.output_dir)
        )
        print("Service directory {} is not a directory".format(
            userargs.output_dir))
        sys.exit(1)

    if not userargs.schema_dir:
        userargs.schema_dir = "{}/{}".format(userargs.service_dir, "schema")

    output_args = {}

    if "parquet" in userargs.outputs:
        validate_parquet_args(userargs, output_args)

    if "kafka" in userargs.outputs:
        validate_kafka_args(userargs, output_args)

    outputs = init_output_workers(userargs.outputs, output_args)

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    tasks = [
        init_hosts(userargs.hosts_file),
        init_services(userargs.service_dir, userargs.schema_dir, queue),
    ]

    nodes, svcs = loop.run_until_complete(asyncio.gather(*tasks))

    for svc in svcs:
        svc.set_nodes(nodes)

    logging.info("Suzieq Started")

    if userargs.service_only:
        svclist = userargs.service_only.split(",")
    else:
        svclist = [svc.name for svc in svcs]

    working_svcs = [svc for svc in svcs if svc.name in svclist]

    try:
        tasks = [svc.run() for svc in working_svcs]
        tasks.append(run_output_worker(queue, outputs))
        loop.run_until_complete(asyncio.gather(*tasks))
        # loop.run_until_complete(svcs[2].run())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt. Terminating")
        loop.close()
        sys.exit(0)


if __name__ == "__main__":

    homedir = str(Path.home())
    supported_outputs = ["parquet", "kafka"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run in foreground, not as daemon",
    )
    parser.add_argument(
        "-k",
        "--kafka-servers",
        default="",
        type=str,
        help="Comma separated list of kafka servers/port",
    )
    parser.add_argument(
        "-H",
        "--hosts-file",
        type=str,
        default="{}/{}".format(homedir, "suzieq-hosts.yml"),
        help="FIle with URL of hosts to observe",
    )
    parser.add_argument(
        "-P",
        "--password-file",
        type=str,
        default="{}/{}".format(homedir, "suzieq-pwd.yml"),
        help="FIle with passwords",
    )
    parser.add_argument(
        "-S",
        "--service-dir",
        type=str,
        required=True,
        help="Directory with services definitions",
    )
    parser.add_argument(
        "-T",
        "--schema-dir",
        type=str,
        default="",
        help="Directory with schema definition for services",
    )
    parser.add_argument(
        "-o",
        "--outputs",
        nargs="+",
        default=["parquet"],
        choices=supported_outputs,
        help="Output formats to write to: kafka, parquet. Use "
        "this option multiple times for more than one output",
    )
    parser.add_argument(
        "-O",
        "--output-dir",
        type=str,
        default="",
        help="Directory to store parquet output in",
    )
    parser.add_argument(
        "-l",
        "--log",
        type=str,
        default="WARNING",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging message level, default is WARNING",
    )
    parser.add_argument(
        "-s",
        "--service-only",
        type=str,
        help="Only run this comma separated list of services",
    )

    userargs = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(userargs.log.upper())
    fh = logging.FileHandler("/tmp/suzieq.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s " "- %(message)s"
    )
    logger.handlers = [fh]
    fh.setFormatter(formatter)

    if userargs.foreground:
        _main(userargs)
    else:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                pid = f.read().strip()
                if not pid.isdigit():
                    os.remove(PID_FILE)
                else:
                    try:
                        os.kill(int(pid), 0)
                    except OSError:
                        os.remove(PID_FILE)
                    else:
                        print(
                            "Another process instance of Suzieq exists with "
                            "pid {}".format(pid)
                        )
        with daemon.DaemonContext(
            files_preserve=[fh.stream], pidfile=pidfile.TimeoutPIDLockFile(
                PID_FILE)
        ):
            _main(userargs)
