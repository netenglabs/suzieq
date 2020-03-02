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

    return None


def load_sq_config(validate=True, config_file=None):
    """Load (and validate) basic suzieq config"""

    # Order of looking up suzieq config:
    #   Current directory
    #   ${HOME}/.suzieq/

    cfgfile = None
    cfg = None

    if config_file:
        cfgfile = config_file
    elif os.path.exists("./suzieq-cfg.yml"):
        cfgfile = "./suzieq-cfg.yml"
    elif os.path.exists(os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"):
        cfgfile = os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"

    if cfgfile:
        with open(cfgfile, "r") as f:
            cfg = yaml.safe_load(f.read())

        if validate:
            validate_sq_config(cfg, sys.stderr)

    if not cfg:
        print(f"suzieq requires a configuration file either in ~/.suzieq-cfg.yml or ./suzieq/suzieq-cfg.yml")
        exit(1)

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


class Schema(object):
    def __init__(self, schema=None, schema_dir=None):
        if schema:
            self._schema = schema
        else:
            self._schema = get_schemas(schema_dir)
        if not self._schema:
            raise ValueError("Must supply either schema or schema directory")

    def tables(self):
        return self._schema.keys()

    def fields_for_table(self, table):
        return [f['name'] for f in self._schema[table]]

    def field_for_table(self, table, field):
        for f in self._schema[table]:
            if f['name'] == field:
                return f

    def key_fields_for_table(self, table):
        # return [f['name'] for f in self._schema[table] if f.get('key', None) is not None]
        return self._sort_fields_for_table(table, 'key')

    def sorted_display_fields_for_table(self, table):
        return self._sort_fields_for_table(table, 'display')

    def _sort_fields_for_table(self, table, tag):
        fields = self.fields_for_table(table)
        field_weights = {}
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if field.get(tag, None) is not None:
                field_weights[f_name] = field.get(tag, 1000)
        return [k for k in sorted(field_weights.keys(), key=lambda x: field_weights[x])]

    def array_fields_for_table(self, table):
        fields = self.fields_for_table(table)
        arrays = []
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if isinstance(field['type'], dict) and field['type'].get('type', None) == 'array':
                arrays.append(f_name)
        return arrays


class SchemaForTable(object):
    def __init__(self, table, schema=None, schema_dir=None):
        if schema:
            self._all_schemas = Schema(schema=schema)
        else:
            self._all_schemas = Schema(schema_dir=schema_dir)
        self._table = table
        if table not in self._all_schemas.tables():
            raise ValueError(f"Unknown table {table}, no schema found for it")

    @property
    def fields(self):
        return self._all_schemas.fields_for_table(self._table)

    def key_fields(self):
        return self._all_schemas.key_fields_for_table(self._table)

    def sorted_display_fields(self):
        return self._all_schemas.sorted_display_fields_for_table(self._table)

    @property
    def array_fields(self):
        return self._all_schemas.array_fields_for_table(self._table)

    def field(self, field):
        return self._all_schemas.field_for_table(self._table, field)

    def get_display_fields(self, columns: list) -> list:
        """Return the list of display fields for the given table"""
        if columns == ["default"]:
            fields = self.sorted_display_fields()

            if "datacenter" not in fields:
                fields.insert(0, "datacenter")
        elif columns == ["*"]:
            fields = self.fields
        else:
            fields = [f for f in columns if f in self.fields]

        return fields


def get_latest_files(folder, start="", end="", view="latest") -> list:
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
            flst = get_latest_ts_dirs(dirs, ssecs, esecs, view)
            ts_dirs = True
        elif files and not ts_dirs:
            flst = get_latest_pq_files(files, root, ssecs, esecs, view)
            pq_files = True

        if flst:
            lsd.append(os.path.join(root, flst[-1]))

    return lsd


def get_latest_ts_dirs(dirs, ssecs, esecs, view):
    newdirs = None

    if not ssecs and not esecs:
        dirs.sort(key=lambda x: int(x.split("=")[1]))
        newdirs = dirs
    elif ssecs and not esecs:
        newdirs = list(filter(lambda x: int(x.split("=")[1]) > ssecs, dirs))
        if not newdirs and view != "changes":
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
        if not newdirs and view != "changes":
            # FInd the entry most adjacent to this one
            newdirs = list(filter(lambda x: int(x.split("=")[1]) < ssecs, dirs))

    return newdirs


def get_latest_pq_files(files, root, ssecs, esecs, view):

    newfiles = None

    if not ssecs and not esecs:
        files.sort(key=lambda x: os.path.getctime("%s/%s" % (root, x)))
        newfiles = files
    elif ssecs and not esecs:
        newfiles = list(
            filter(lambda x: os.path.getctime("%s/%s" % (root, x)) > ssecs, files)
        )
        if not newfiles and view != "changes":
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
        if not newfiles and view != "changes":
            # Find the entry most adjacent to this one
            newfiles = list(
                filter(lambda x: os.path.getctime("%s/%s" % (root, x)) < ssecs, files)
            )
    return newfiles
