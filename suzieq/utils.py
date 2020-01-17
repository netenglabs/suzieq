import os
import sys
from pathlib import Path
import logging
import json
import yaml

import pandas as pd


def validate_sq_config(cfg, fh):
    """Validate Suzieq config file

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file
    fh:  file logger handle

    Returns:
    --------
    status: None if all is good or error string
    """

    ddir = cfg.get("data-directory", None)
    if not ddir:
        return "No data directory for output files specified"

    sdir = cfg.get("service-directory", None)
    if not sdir:
        return "No service config directory specified"

    p = Path(sdir)
    if not p.is_dir():
        return "Service directory {} is not a directory".format(sdir)

    scdir = cfg.get("service-directory", None)
    if not scdir:
        scdir = sdir + "/schema"
        cfg["schema-directory"] = scdir

    p = Path(scdir)
    if not p.is_dir():
        return "Invalid schema directory specified"

    ksrv = cfg.get("kafka-servers", None)
    if ksrv:
        from confluent_kafka import Consumer, KafkaException

        kc = Consumer({"bootstrap.servers": ksrv}, logger=fh)

        try:
            kc.list_topics(timeout=1)
        except KafkaException as e:
            return "Kafka server error: {}".format(str(e))

        kc.close()

    return None


def load_sq_config(validate=True):
    """Load (and validate) basic suzieq config"""

    # Order of looking up suzieq config:
    #   Current directory
    #   ${HOME}/.suzieq/

    cfgfile = None
    cfg = None

    if os.path.exists("./suzieq-cfg.yml"):
        cfgfile = "./suzieq-cfg.yml"
    elif os.path.exists(os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"):
        cfgfile = os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"

    if cfgfile:
        with open(cfgfile, "r") as f:
            cfg = yaml.safe_load(f.read())

        if validate:
            validate_sq_config(cfg, sys.stderr)

    return cfg


def get_schemas(schema_dir):

    schemas = {}

    if not os.path.exists(schema_dir):
        logging.error("Schema directory {} does not exist".format(schema_dir))
        return schemas

    for root, _, files in os.walk(schema_dir):
        for topic in files:
            with open(root + "/" + topic, "r") as f:
                data = json.loads(f.read())
                schemas[data["name"]] = data["fields"]
        break

    return schemas


def get_display_fields(table: str, columns: list, schema: dict) -> list:
    """Return the list of display fields for the given table"""

    if columns == ["default"]:
        fields = [
            f["name"]
            for f in sorted(schema, key=lambda x: x.get("display", 1000))
            if f.get("display", None)
        ]

        if "datacenter" not in fields:
            fields.insert(0, "datacenter")

    elif columns == ["*"]:
        fields = [f["name"] for f in schema]
    else:
        sch_flds = [f["name"] for f in schema]

        fields = [f for f in columns if f in sch_flds]

    return fields


def get_latest_files(folder, start="", end="") -> list:
    lsd = []

    if start:
        ssecs = pd.to_datetime(start, infer_datetime_format=True).timestamp() * 1000
    else:
        ssecs = 0

    if end:
        esecs = pd.to_datetime(end, infer_datetime_format=True).timestamp() * 1000
    else:
        esecs = 0

    ts_dirs = False
    pq_files = False

    for root, dirs, files in os.walk(folder):
        flst = None
        if dirs and dirs[0].startswith("timestamp") and not pq_files:
            flst = get_latest_ts_dirs(dirs, ssecs, esecs)
            ts_dirs = True
        elif files and not ts_dirs:
            flst = get_latest_pq_files(files, root, ssecs, esecs)
            pq_files = True

        if flst:
            lsd.append(os.path.join(root, flst[-1]))

    return lsd


def get_latest_ts_dirs(dirs, ssecs, esecs):
    newdirs = None

    if not ssecs and not esecs:
        dirs.sort(key=lambda x: int(x.split("=")[1]))
        newdirs = dirs
    elif ssecs and not esecs:
        newdirs = list(filter(lambda x: int(x.split("=")[1]) > ssecs, dirs))
        if not newdirs:
            # FInd the entry most adjacent to this one
            newdirs = list(filter(lambda x: int(x.split("=")[1]) < ssecs, dirs))
    elif esecs and not ssecs:
        newdirs = list(filter(lambda x: int(x.split("=")[1]) < esecs, dirs))
    else:
        newdirs = list(
            filter(
                lambda x: int(x.split("=")[1]) < esecs and int(x.split("=")[1]) > ssecs,
                dirs,
            )
        )
        if not newdirs:
            # FInd the entry most adjacent to this one
            newdirs = list(filter(lambda x: int(x.split("=")[1]) < ssecs, dirs))

    return newdirs


def get_latest_pq_files(files, root, ssecs, esecs):

    newfiles = None

    if not ssecs and not esecs:
        files.sort(key=lambda x: os.path.getctime("%s/%s" % (root, x)))
        newfiles = files
    elif ssecs and not esecs:
        newfiles = list(
            filter(lambda x: os.path.getctime("%s/%s" % (root, x)) > ssecs, files)
        )
        if not newfiles:
            # FInd the entry most adjacent to this one
            newfiles = list(
                filter(
                    lambda x: os.path.getctime("{}/{}".format(root, x)) < ssecs, files
                )
            )
    elif esecs and not ssecs:
        newfiles = list(
            filter(lambda x: os.path.getctime("%s/%s" % (root, x)) < esecs, files)
        )
    else:
        newfiles = list(
            filter(
                lambda x: os.path.getctime("%s/%s" % (root, x)) < esecs
                and os.path.getctime("%s/%s" % (root, x)) > ssecs,
                files,
            )
        )
        if not newfiles:
            # Find the entry most adjacent to this one
            newfiles = list(
                filter(lambda x: os.path.getctime("%s/%s" % (root, x)) < ssecs, files)
            )
    return newfiles
