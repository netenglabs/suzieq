import os
import re
import sys
from pathlib import Path
import logging
import json
import yaml
from dateutil.relativedelta import relativedelta
from datetime import datetime

import pandas as pd
import pyarrow as pa


logger = logging.getLogger(__name__)


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
        print(f"suzieq requires a configuration file either in ./suzieq-cfg.yml "
              "or ~/suzieq/suzieq-cfg.yml")
        exit(1)

    return cfg


class Schema(object):
    def __init__(self, schema_dir):
        self._init_schemas(schema_dir)
        if not self._schema:
            raise ValueError("Unable to get schemas")

    def _init_schemas(self, schema_dir: str):
        """Returns the schema definition which is the fields of a table"""

        schemas = {}
        phy_tables = {}
        types = {}

        if not (schema_dir and os.path.exists(schema_dir)):
            logger.error(
                "Schema directory {} does not exist".format(schema_dir))
            raise Exception(f"Schema directory {schema_dir} does not exist")

        for root, _, files in os.walk(schema_dir):
            for topic in files:
                if not topic.endswith(".avsc"):
                    continue
                with open(root + "/" + topic, "r") as f:
                    data = json.loads(f.read())
                    table = data["name"]
                    schemas[table] = data["fields"]
                    types[table] = data['type']
                    phy_tables[data["name"]] = data.get("physicalTable", table)
            break

        self._schema = schemas
        self._phy_tables = phy_tables
        self._types = types

    def tables(self):
        return self._schema.keys()

    def fields_for_table(self, table):
        return [f['name'] for f in self._schema[table]]

    def get_raw_schema(self, table):
        return self._schema[table]

    def field_for_table(self, table, field):
        for f in self._schema[table]:
            if f['name'] == field:
                return f

    def type_for_table(self, table):
        return self._types[table]

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
        return [k for k in sorted(field_weights.keys(),
                                  key=lambda x: field_weights[x])]

    def array_fields_for_table(self, table):
        fields = self.fields_for_table(table)
        arrays = []
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if isinstance(field['type'], dict) and field['type'].get('type', None) == 'array':
                arrays.append(f_name)
        return arrays

    def get_phy_table_for_table(self, table):
        """Return the name of the underlying physical table"""
        if self._phy_tables:
            return self._phy_tables.get(table, table)

    def get_partition_columns_for_table(self, table):
        """Return the list of partition columns for table"""
        if self._phy_tables:
            return self._sort_fields_for_table(table, 'partition')

    def get_arrow_schema(self, table):
        """Convert the internal AVRO schema into the equivalent PyArrow schema"""

        avro_sch = self._schema.get(table, None)
        if not avro_sch:
            raise AttributeError(f"No schema found for {table}")

        arsc_fields = []

        map_type = {
            "string": pa.string(),
            "long": pa.int64(),
            "int": pa.int32(),
            "double": pa.float64(),
            "float": pa.float32(),
            "timestamp": pa.int64(),
            "timedelta64[s]": pa.float64(),
            "boolean": pa.bool_(),
            "array.string": pa.list_(pa.string()),
            "array.nexthopList": pa.list_(pa.struct([('nexthop', pa.string()),
                                                     ('oif', pa.string()),
                                                     ('weight', pa.int32())])),
            "array.long": pa.list_(pa.int64()),
            "array.float": pa.list_(pa.float32()),
        }

        for fld in avro_sch:
            if isinstance(fld["type"], dict):
                if fld["type"]["type"] == "array":
                    if fld["type"]["items"]["type"] == "record":
                        avtype: str = "array.{}".format(fld["name"])
                    else:
                        avtype: str = "array.{}".format(
                            fld["type"]["items"]["type"])
                else:
                    # We don't support map yet
                    raise AttributeError
            else:
                avtype: str = fld["type"]

            arsc_fields.append(pa.field(fld["name"], map_type[avtype]))

        return pa.schema(arsc_fields)


class SchemaForTable(object):
    def __init__(self, table, schema: Schema = None, schema_dir=None):
        if schema:
            if isinstance(schema, Schema):
                self._all_schemas = schema
            else:
                raise ValueError("Passing non-Schema type for schema")
        else:
            self._all_schemas = Schema(schema_dir=schema_dir)
        self._table = table
        if table not in self._all_schemas.tables():
            raise ValueError(f"Unknown table {table}, no schema found for it")

    @property
    def type(self):
        return self._all_schemas.type_for_table(self._table)

    @property
    def version(self):
        return self._all_schemas.field_for_table(self._table,
                                                 'sqvers')['default']

    @property
    def fields(self):
        return self._all_schemas.fields_for_table(self._table)

    def get_phy_table(self):
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_partition_columns(self):
        return self._all_schemas.get_partition_columns_for_table(self._table)

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

            if "namespace" not in fields:
                fields.insert(0, "namespace")
        elif columns == ["*"]:
            fields = self.fields
        else:
            fields = [f for f in columns if f in self.fields]

        return fields

    def get_phy_table_for_table(self) -> str:
        """Return the underlying physical table for this logical table"""
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_raw_schema(self):
        return self._all_schemas.get_raw_schema(self._table)

    def get_arrow_schema(self):
        return self._all_schemas.get_arrow_schema(self._table)


def get_latest_files(folder, start="", end="", view="latest") -> list:
    lsd = []

    if start:
        ssecs = pd.to_datetime(
            start, infer_datetime_format=True).timestamp() * 1000
    else:
        ssecs = 0

    if end:
        esecs = pd.to_datetime(
            end, infer_datetime_format=True).timestamp() * 1000
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
            newdirs = list(filter(lambda x: int(
                x.split("=")[1]) < ssecs, dirs))
    elif esecs and not ssecs:
        newdirs = list(filter(lambda x: int(x.split("=")[1]) < esecs, dirs))
    else:
        newdirs = list(
            filter(
                lambda x: int(x.split("=")[1]) < esecs and int(
                    x.split("=")[1]) > ssecs,
                dirs,
            )
        )
        if not newdirs and view != "changes":
            # FInd the entry most adjacent to this one
            newdirs = list(filter(lambda x: int(
                x.split("=")[1]) < ssecs, dirs))

    return newdirs


def get_latest_pq_files(files, root, ssecs, esecs, view):

    newfiles = None

    if not ssecs and not esecs:
        files.sort(key=lambda x: os.path.getctime("%s/%s" % (root, x)))
        newfiles = files
    elif ssecs and not esecs:
        newfiles = list(
            filter(lambda x: os.path.getctime(
                "%s/%s" % (root, x)) > ssecs, files)
        )
        if not newfiles and view != "changes":
            # FInd the entry most adjacent to this one
            newfiles = list(
                filter(
                    lambda x: os.path.getctime(
                        "{}/{}".format(root, x)) < ssecs, files
                )
            )
    elif esecs and not ssecs:
        newfiles = list(
            filter(lambda x: os.path.getctime(
                "%s/%s" % (root, x)) < esecs, files)
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
                filter(lambda x: os.path.getctime(
                    "%s/%s" % (root, x)) < ssecs, files)
            )
    return newfiles


def calc_avg(oldval, newval):
    if not oldval:
        return newval

    return float((oldval+newval)/2)


def get_timestamp_from_cisco_time(input, timestamp):
    """Get timestamp in ms from the Cisco-specific timestamp string
    Examples of Cisco timestamp str are P2DT14H45M16S, P1M17DT4H49M50S etc.
    """
    if not input.startswith('P'):
        return 0
    months = days = hours = mins = secs = 0

    day, timestr = input[1:].split('T')

    if 'Y' in day:
        years, day = day.split('Y')
        months = int(years)*12

    if 'M' in day:
        mnt, day = day.split('M')
        months = months + int(mnt)
    if 'D' in day:
        days = int(day.split('D')[0])

    if 'H' in timestr:
        hours, timestr = timestr.split('H')
        hours = int(hours)
    if 'M' in timestr:
        mins, timestr = timestr.split('M')
        mins = int(mins)
    if 'S' in timestr:
        secs = timestr.split('S')[0]
        secs = int(secs)

    delta = relativedelta(months=months, days=days,
                          hours=hours, minutes=mins, seconds=secs)
    return int((datetime.fromtimestamp(timestamp)-delta).timestamp()*1000)


def get_timestamp_from_junos_time(input, timestamp: int):
    """Get timestamp in ms from the Junos-specific timestamp string
    The expected input looks like: "attributes" : {"junos:seconds" : "0"}.
    We don't check for format because we're assuming the input would be blank
    if it wasn't the right format. The input can either be a dictionary or a
    JSON string.
    """

    if not input:
        # Happens for logical interfaces such as gr-0/0/0
        secs = 0
    else:
        try:
            if isinstance(input, str):
                data = json.loads(input)
            else:
                data = input
            secs = int(data.get('junos:seconds', 0))
        except Exception:
            logger.warning(f'Unable to convert junos secs from {input}')
            secs = 0

    delta = relativedelta(seconds=int(secs))
    return int((datetime.fromtimestamp(timestamp)-delta).timestamp()*1000)


def convert_macaddr_format_to_colon(macaddr):
    """COnvert NXOS/EOS . macaddr form to standard : format"""
    if (isinstance(macaddr, str) and
            re.match(r'[0-9a-z]{4}.[0-9a-z]{4}.[0-9a-z]{4}', macaddr)):
        return ':'.join([f'{x[:2]}:{x[2:]}' for x in macaddr.split('.')])

    return('00:00:00:00:00:00')


def convert_rangestring_to_list(rangestr: str) -> list:
    """Convert a range list such as '1, 2-5, 10, 12-20' to list
    """

    tmplst = []
    if not isinstance(rangestr, str):
        return tmplst

    try:
        for x in rangestr.split(','):
            x = x.strip().split('-')
            if x[0]:
                if len(x) == 2:
                    intrange = list(range(int(x[0]), int(x[1])+1))
                    tmplst.extend(intrange)
                else:
                    tmplst.append(int(x[0]))
    except Exception:
        logger.error(f"Range string parsing failed for {rangestr}")
        return []
    return tmplst


def build_query_str(skip_fields: list, schema, **kwargs) -> str:
    """Build a pandas query string given key/val pairs
    """
    query_str = ''
    prefix = ''

    def build_query_str(fld, fldtype) -> str:
        """Builds the string from the provided user input"""

        if ((fldtype == "long" or fldtype == "float") and not
                isinstance(fld, str)):
            result = f'=={fld}'

        elif fld.startswith('!'):
            fld = fld[1:]
            if fldtype == "long" or fldtype == "float":
                result = f'!= {fld}'
            else:
                result = f'!= "{fld}"'
        elif fld.startswith('<') or fld.startswith('>'):
            result = fld
        else:
            result = f'=="{fld}"'

        return result

    for f, v in kwargs.items():
        if not v or f in skip_fields or f in ["groupby"]:
            continue
        type = schema.field(f).get('type', 'string')
        if isinstance(v, list) and len(v):
            subq = ''
            subcond = ''
            for elem in v:
                subq += f'{subcond} {f}{build_query_str(elem, type)} '
                subcond = 'or'
            query_str += '{} ({})'.format(prefix, subq)
            prefix = "and"
        else:
            query_str += f'{prefix} {f}{build_query_str(v, type)} '
            prefix = "and"

    return query_str


def known_devtypes() -> list:
    """Returns the list of known dev types"""
    return(['cumulus', 'eos', 'junos-mx', 'junos-qfx', 'junos-ex', 'linux', 'nxos', 'sonic'])
