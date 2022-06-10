import errno
import fcntl
import getpass
import json
import logging
import os
import re
import sys
from datetime import datetime
from enum import Enum
from importlib.util import find_spec
from ipaddress import ip_network
from itertools import groupby
from logging.handlers import RotatingFileHandler
from os import getenv
from typing import Dict, List
from tzlocal import get_localzone

import pandas as pd
import yaml
from dateparser import parse
from dateutil.relativedelta import relativedelta
from pytz import all_timezones
from suzieq.shared.exceptions import SensitiveLoadError
from suzieq.version import SUZIEQ_VERSION

logger = logging.getLogger(__name__)
MAX_MTU = 9216
# MISSING_SPEED: the interface doesn't provide a speed and I have to complain
# NO_SPEED: the interface doesn't provide a speed but I don't care
#           (for example virtual interfaces)
# MISSING_SPEED_IF_TYPES: list of interface-types that will have MISSING_SPEED
#                         if the speed is invalid.
#                         Types which are not in this list will have NO_SPEED
MISSING_SPEED = -1
NO_SPEED = 0
MISSING_SPEED_IF_TYPES = ['ethernet', 'bond', 'bond_slave']
SUPPORTED_ENGINES = ['pandas', 'rest']
DATA_FORMATS = ["text", "json", "csv", "markdown"]


class PollerTransport(str, Enum):
    """Supported poller transoport enum"""
    ssh = 'ssh'
    https = 'https'


def validate_sq_config(cfg):
    """Validate Suzieq config file

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file

    Returns:
    --------
    status: None if all is good or error string
    """

    if not isinstance(cfg, dict):
        return "FATAL: Invalid config file format"

    ddir = cfg.get("data-directory", None)
    if not ddir:
        return "FATAL: No data directory for output files specified"

    if not os.path.isdir(ddir):
        os.makedirs(ddir, exist_ok=True)

    if (not os.path.isdir(ddir) or not (os.access(ddir, os.R_OK | os.W_OK |
                                                  os.EX_OK))):
        if os.getenv('SQENV', None) == 'docker':
            return f'FATAL: Data directory {ddir} is not an accessible ' \
                'dir.\nIt looks like you are using docker, make sure that ' \
                'the mounted volume has the proper permissions.\nYou can ' \
                'update the permissions using the following command:\n\n' \
                'docker run --user root -v samples_parquet-db:/home/suzieq'\
                '/parquet --rm netenglabs/suzieq -c "chown -R ' \
                '1000:1000 parquet"'
        else:
            return f'FATAL: Data directory {ddir} is not an accessible dir'

    # Locate the service and schema directories
    svcdir = cfg.get('service-directory', None)
    if (not (svcdir and os.path.isdir(ddir) and
             os.access(svcdir, os.R_OK | os.W_OK | os.EX_OK))):
        sqdir = get_sq_install_dir()
        svcdir = f'{sqdir}/config'
        if os.access(svcdir, os.R_OK | os.EX_OK):
            cfg['service-directory'] = svcdir
        else:
            svcdir = None

    if not svcdir:
        return 'FATAL: No service directory found'

    schemadir = cfg.get('schema-directory', None)
    if not (schemadir and os.access(schemadir, os.R_OK | os.EX_OK)):
        schemadir = f'{svcdir}/schema'
        if os.access(schemadir, os.R_OK | os.EX_OK):
            cfg['schema-directory'] = schemadir
        else:
            schemadir = None

    if not schemadir:
        return 'FATAL: No schema directory found'

    # Move older format logging level and period to appropriate new location
    if 'poller' not in cfg:
        cfg['poller'] = {}

    for knob in ['logging-level', 'period']:
        if knob in cfg:
            cfg['poller'][knob] = cfg[knob]

    if 'rest' not in cfg:
        cfg['rest'] = {}

    for knob in ['API_KEY', 'rest_certfile', 'rest_keyfile']:
        if knob in cfg:
            cfg['rest'][knob] = cfg[knob]

    error = _load_rest_api_key(cfg)
    if error:
        return error

    # Verify timezone if present is valid
    def_tz = get_localzone().zone
    reader = cfg.get('analyzer', {})
    if reader and isinstance(reader, dict):
        usertz = reader.get('timezone', '')
        if usertz and usertz not in all_timezones:
            return f'Invalid timezone: {usertz}'
        elif not usertz:
            reader['timezone'] = def_tz
    else:
        cfg['analyzer'] = {'timezone': def_tz}

    return None


def _load_rest_api_key(cfg: Dict) -> str:
    """Loads the rest api key into the config

    Args:
        cfg (Dict): SuzieQ config

    Returns:
        str: Empty if the variable was loaded correctly,
        the error otherwise
    """
    if 'rest' in cfg and 'API_KEY' in cfg['rest']:
        api_key = cfg['rest']['API_KEY']
        if api_key == 'ask':
            # this function is called during the on_connect of the cli
            # Nubia doesn't allow the user to prompt anything at that point
            return "'ask' option is not available for REST API KEY"
        try:
            cfg['rest']['API_KEY'] = get_sensitive_data(api_key)
        except SensitiveLoadError as e:
            return f'Cannot load REST API KEY: {e}'
    return ''


def load_sq_config(validate=True, config_file=None):
    """Load (and validate) basic suzieq config"""

    # Order of looking up suzieq config:
    #   Current directory
    #   ${HOME}/.suzieq/

    cfgfile = None
    cfg = {}

    cfgfile = sq_get_config_file(config_file)

    if cfgfile:
        try:
            with open(cfgfile, "r") as f:
                cfg = yaml.safe_load(f.read())
        except Exception as e:  # pylint: disable=broad-except
            print(f'ERROR: Unable to open config file {cfgfile}: {e.args[1]}')
            sys.exit(1)

        if not cfg:
            print(f'ERROR: Empty config file {cfgfile}')
            sys.exit(1)

        if validate:
            error_str = validate_sq_config(cfg)
            if error_str:
                print(f'ERROR: Invalid config file: {cfgfile}')
                print(error_str)
                sys.exit(1)
        else:
            # also without validation, I need to load the REST API key and,
            # if necessary, raise an error
            error = _load_rest_api_key(cfg)
            if error:
                print(f'ERROR: Invalid config file: {cfgfile}')
                print(error)
                sys.exit(1)

    if not cfg:
        print("suzieq requires a configuration file either in "
              "./suzieq-cfg.yml or ~/.suzieq/suzieq-cfg.yml")
        sys.exit(1)

    return cfg


def get_sensitive_data(input_method: str, ask_message: str = '') -> str:
    """This function is used by the inventory to specify sensitive data

    The valid methods are:
        - 'plain:' (default): copy the content of input (can be omitted)
        - 'env:': get the information from an environment variable
        - 'ask': write the information on the stdin

    Args:
        input_method (str): string with info for the sensitive value
        ask_message (str): message to prompt for the 'ask' method

    Raises:
        EnvVarLoadError: environment variable not found

    Returns:
        str: sensitive data
    """
    if not input_method:
        return input_method
    sens_data = input_method
    if input_method.startswith('env:'):
        input_method = input_method.split('env:')[1].strip()
        sens_data = getenv(input_method, '')
        if not sens_data:
            raise SensitiveLoadError(
                f'No environment variable called '
                f"'{input_method}'")
    elif input_method.startswith('plain:'):
        sens_data = input_method.split("plain:")[1].strip()
    elif input_method.startswith('ask'):
        sens_data = getpass.getpass(ask_message)
    return sens_data


def sq_get_config_file(config_file):
    """Get the path to the suzieq config file"""

    if config_file:
        cfgfile = config_file
    elif os.path.exists("./suzieq-cfg.yml"):
        cfgfile = "./suzieq-cfg.yml"
    elif os.path.exists(os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"):
        cfgfile = os.getenv("HOME") + "/.suzieq/suzieq-cfg.yml"
    else:
        cfgfile = None
    return cfgfile


def get_latest_files(folder, start="", end="", view="latest") -> list:
    '''Get list of relevant parquet files from folder'''
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
    '''Get latest timestamp directories in a folder'''
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
    '''Get the latest parquet files given a fileset/start & end times & view'''
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
    '''Calculate average of old and new'''

    if not oldval:
        return newval

    return float((oldval+newval)/2)


def get_timestamp_from_cisco_time(in_data, timestamp) -> int:
    """Get timestamp in ms from the Cisco-specific timestamp string
    Examples of Cisco timestamp str are P2DT14H45M16S, P1M17DT4H49M50S etc.
    """
    if in_data and not in_data.startswith('P'):
        in_data = in_data.replace('y', 'years')
        in_data = in_data.replace('w', 'weeks')
        in_data = in_data.replace('d', 'days')

        other_time = parse(in_data,
                           settings={'RELATIVE_BASE':
                                     datetime.utcfromtimestamp(timestamp)})
        if other_time:
            return int(other_time.timestamp()*1000)
        else:
            logger.error(f'Unable to parse relative time string, {in_data}')
            return 0

    months = days = hours = mins = secs = 0

    if 'T' in in_data:
        day, timestr = in_data[1:].split('T')
    else:
        day = in_data[1:]
        timestr = ''

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


def get_timestamp_from_junos_time(in_data, timestamp: int):
    """Get timestamp in ms from the Junos-specific timestamp string
    The expected input looks like: "attributes" : {"junos:seconds" : "0"}.
    We don't check for format because we're assuming the input would be blank
    if it wasn't the right format. The input can either be a dictionary or a
    JSON string.
    """

    if not in_data:
        # Happens for logical interfaces such as gr-0/0/0
        secs = 0
    else:
        try:
            if isinstance(in_data, str):
                data = json.loads(in_data)
            else:
                data = in_data
            secs = int(data.get('junos:seconds', 0))
        except Exception:  # pylint: disable=broad-except
            logger.warning(f'Unable to convert junos secs from {in_data}')
            secs = 0

    delta = relativedelta(seconds=int(secs))
    return int((datetime.fromtimestamp(timestamp)-delta).timestamp()*1000)


def convert_macaddr_format_to_colon(macaddr: str) -> str:
    """Convert various macaddr forms to standard ':' format, lowecase

    One unexpected side-effect, it'll convert the given string to lowercase
    even if it doesn't match a macaddr.

    :param macaddr: str, the macaddr string to convert
    :returns: the converted macaddr string or all 0s string if arg not str
    :rtype: str

    """
    if isinstance(macaddr, str):
        macaddr = macaddr.lower()
        if re.match(r'[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}', macaddr):
            return (':'.join([f'{x[:2]}:{x[2:]}'
                              for x in macaddr.split('.')]))
        if re.match(r'[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-'
                    r'[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}',
                    macaddr):
            return macaddr.replace('-', ':')
        if re.match(r'[0-9a-f]{4}:[0-9a-f]{4}:[0-9a-f]{4}', macaddr):
            return (':'.join([f'{x[:2]}:{x[2:]}'
                              for x in macaddr.split(':')]))
        if ':' not in macaddr and re.match(r'[0-9a-f]{12}', macaddr):
            newmac = ''
            for i in range(0, 12, 2):
                newmac += f'{macaddr[i:i+2]}:'
            newmac = newmac[:-1]  # remove the trailing ':'
            return newmac
        if re.match(r'[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}', macaddr):
            return (':'.join([f'{x[:2]}:{x[2:]}'
                              for x in macaddr.split('-')]))
        return macaddr

    return '00:00:00:00:00:00'


def validate_network(network: str) -> bool:
    """Validate network address

    Args:
        network: (str) the network id to validate

    Returns:
        bool: A boolean with the result of the validation

    """
    try:
        if isinstance(network, str) and '/' in network:
            ip_network(network)
            return True
        return False
    except ValueError:
        return False


def validate_macaddr(macaddr: str) -> bool:
    """Validate mac address

    Args:
        macaddr: (str) the macaddr string to validate

    Returns:
        bool: A boolean with the result of the validation

    """
    if isinstance(macaddr, str):
        macaddr = convert_macaddr_format_to_colon(macaddr)
        if re.fullmatch(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', macaddr):
            return True

    return False


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
    except Exception:  # pylint: disable=broad-except
        logger.error(f"Range string parsing failed for {rangestr}")
        return []
    return tmplst


def convert_numlist_to_ranges(numList: List[int]) -> str:
    """Convert a given list of numbers into a range string

    Args:
        numList (List[int]): unsorted/sorted list of integers

    Returns:
        str: Range string such as '1-5, 10, 12-20'
    """
    result = ''
    for _, b in groupby(enumerate(sorted(numList)),
                        lambda pair: pair[1] - pair[0]):
        b = list(b)
        if len(b) > 1:
            result += f'{b[0][1]}-{b[-1][1]}, '
        else:
            result += f'{b[0][1]}, '

    return result[:-2]


def build_query_str(skip_fields: list, schema, ignore_regex=True,
                    **kwargs) -> str:
    """Build a pandas query string given key/val pairs
    """
    query_str = ''
    prefix = ''

    def _build_query_str(fld, val, fldtype) -> List[str]:
        """Builds the string from the provided user input

        Besides handling operators and regexp, the function returns what
        the subsequent match within this list needs to be. If the ! operator
        is used, we have to switch to AND, else we can be at OR. For
        example. it makes no sense to say !leaf01 OR !leaf02 as this will
        include both leaf01 and leaf02.
        """

        cond = 'or'
        num_type = ["long", "float", "int"]
        if ((fldtype in num_type) and not
                isinstance(val, str)):
            result = f'{fld} == {val}'

        elif val.startswith('!'):
            val = val[1:]
            cond = 'and'
            if fldtype in num_type:
                result = f'{fld} != {val}'
            else:
                result = f'{fld} != "{val}"'
        elif val.startswith(('<', '>')):
            result = val
        elif val.startswith('~'):
            val = val[1:]
            if val.startswith('!'):
                val = val[1:]
                cond = 'and'
                result = f'~{fld}.str.match("{val}")'
            else:
                result = f'{fld}.str.match("{val}")'
        else:
            if fldtype in num_type:
                result = f'{fld} == {val}'
            else:
                result = f'{fld} == "{val}"'

        return result, cond

    for f, v in kwargs.items():
        if not v or f in skip_fields or f in ["groupby"]:
            continue

        stype = schema.field(f).get('type', 'string')
        if isinstance(v, list) and len(v):
            notlist = [x for x in v
                       if x.startswith('!') or x.startswith('~!')]
            if notlist != v:
                newv = [x for x in v
                        if not x.startswith('!') and not x.startswith('~!')]
            else:
                newv = v
            subq = ''
            subcond = ''
            if ignore_regex and [x for x in newv
                                 if isinstance(x, str) and
                                 x.startswith('~')]:
                continue

            for elem in newv:
                intq, nextcond = _build_query_str(f, elem, stype)
                subq += f'{subcond} {intq} '
                subcond = nextcond
            query_str += '{} ({})'.format(prefix, subq)
            prefix = "and"
        else:
            intq, nextcond = _build_query_str(f, v, stype)
            query_str += f'{prefix} {intq} '
            prefix = nextcond

    return query_str


def poller_log_params(cfg: dict, is_controller=False, worker_id=0) -> tuple:
    """Get the log file, level and size for the given program from config
    It gets the base file name of the configuration file and appends a prefix
    which depends on the component of the poller

    Args:
        cfg (dict): The config dictionary
        is_controller (bool, optional): If the component is the controller.
            Defaults to False.
        worker_id (int, optional): The poller worker id. Defaults to 0.

    Returns:
        tuple: [description]
    """
    def_logfile = '/tmp/sq-poller.log'
    logfile, loglevel, logsize, log_stdout = get_log_params(
        'poller', cfg, def_logfile)
    file_name = logfile.split('.log')[0]
    if is_controller:
        file_name += '-controller.log'
    else:
        file_name += f'-{worker_id}.log'
    return file_name, loglevel, logsize, log_stdout


def get_log_params(prog: str, cfg: dict, def_logfile: str) -> tuple:
    """Get the log file, level and size for the given program from config

    The logfile is supposed to be defined by a variable called logfile
    within the hierarchy of the config dictionary. Thus, the poller log file
    will be {'poller': {'logfile': '/tmp/sq-poller.log'}}, for example.

    :param prog: str, The name of the program. Valid values are poller,
                      coaelscer, and rest.
    :param cfg: dict, The config dictionary
    :param def_logfile: str, The default log file to return
    :returns: log file name, log level, log size, and
              True/False for logging to stdout
    :rtype: str, str and int

    """
    if cfg:
        logfile = cfg.get(prog, {}).get('logfile', def_logfile)
        loglevel = cfg.get(prog, {}).get('logging-level', 'WARNING')
        logsize = cfg.get(prog, {}).get('logsize', 10000000)
        log_stdout = cfg.get(prog, {}).get('log-stdout', False)
    else:
        logfile = def_logfile
        loglevel = 'WARNING'
        logsize = 10000000
        log_stdout = False

    return logfile, loglevel, logsize, log_stdout


def init_logger(logname: str,
                logfile: str,
                loglevel: str = 'WARNING',
                logsize: int = 10000000,
                use_stdout: bool = False) -> logging.Logger:
    """Initialize the logger

    :param logname: str, the name of the app that's logging
    :param logfile: str, the log file to use
    :param loglevel: str, the default log level to set the logger to
    :param use_stdout: str, log to stdout instead of or in addition to file

    """

    fh = sh = None
    # this needs to be suzieq.poller, so that it is the root of all the
    # other pollers
    log = logging.getLogger(logname)
    log.setLevel(loglevel.upper())
    if logfile:
        fh = RotatingFileHandler(logfile, maxBytes=logsize, backupCount=2)
    if use_stdout:
        sh = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    if fh:
        fh.setFormatter(formatter)
    if sh:
        sh.setFormatter(formatter)

    # set root logger level, so that we set asyncssh log level
    #  asynchssh sets it's level to the root level
    root = logging.getLogger()
    root.setLevel(loglevel.upper())
    if fh:
        root.addHandler(fh)
    if sh:
        root.addHandler(sh)

    log.warning(f"log level {logging.getLevelName(log.level)}")

    return log


def known_devtypes() -> list:
    """Returns the list of known dev types"""
    return(['cumulus', 'eos', 'iosxe', 'iosxr', 'ios', 'junos-mx', 'junos-qfx',
            'junos-qfx10k', 'junos-ex', 'junos-es', 'linux', 'nxos', 'sonic',
            'panos'])


def humanize_timestamp(field: pd.Series, tz=None) -> pd.Series:
    '''Convert the UTC timestamp in Dataframe to local time.
    Use of pd.to_datetime will not work as it converts the timestamp
    to UTC. If the timestamp is already in UTC format, we get busted time.
    '''
    if field.empty:
        return field

    if pd.core.dtypes.common.is_datetime_or_timedelta_dtype(field):
        return field
    if pd.core.dtypes.common.is_datetime64_any_dtype(field):
        return field
    tz = tz or get_localzone().zone
    return field.apply(lambda x: datetime.utcfromtimestamp((int(x)/1000))) \
                .dt.tz_localize('UTC').dt.tz_convert(tz)


def expand_nxos_ifname(ifname: str) -> str:
    '''Expand shortned ifnames in NXOS to their full values, if required'''
    if not ifname:
        return ''
    if ifname.startswith('Eth') and 'Ether' not in ifname:
        return ifname.replace('Eth', 'Ethernet')
    elif ifname.startswith('Po') and 'port' not in ifname:
        return ifname.replace('Po', 'port-channel')
    elif ifname.startswith('Lo') and 'loop' not in ifname:
        return ifname.replace('Lo', 'loopback')
    return ifname


def expand_eos_ifname(ifname: str) -> str:
    '''Expand shortned ifnames in EOS to their full values, if required'''
    if not ifname:
        return ''
    if ifname.startswith('Eth') and 'Ether' not in ifname:
        return ifname.replace('Eth', 'Ethernet')
    elif ifname.startswith('Po') and 'Port' not in ifname:
        return ifname.replace('Po', 'Port-Channel')
    elif ifname.startswith('Vx') and 'Vxlan' not in ifname:
        return ifname.replace('Vx', 'Vxlan')
    return ifname


def ensure_single_instance(filename: str, block: bool = False) -> int:
    """Check there's only a single active instance of a process using lockfile

    It optionally can block waiting for the resource the become available.

    Use a pid file with advisory file locking to assure this.

    :returns: fd if lock was successful or 0
    :rtype: int

    """
    basedir = os.path.dirname(filename)
    if not os.path.exists(basedir):
        # Permission error or any other error will abort
        os.makedirs(basedir, exist_ok=True)

    fd = os.open(filename, os.O_RDWR | os.O_CREAT, 0o600)
    if fd:
        try:
            if block:
                fcntl.flock(fd, fcntl.LOCK_EX)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.truncate(fd, 0)
            os.write(fd, bytes(str(os.getpid()), 'utf-8'))
        except OSError:
            if OSError.errno == errno.EBUSY:
                # Return the PID of the process thats locked the file
                bpid = os.read(fd, 10)
                os.close(fd)
                try:
                    fd = -int(bpid)
                except ValueError:
                    fd = 0
            else:
                os.close(fd)
                fd = 0

    return fd


def expand_ios_ifname(ifname: str) -> str:
    """Get expanded interface name for IOSXR/XE given its short form

    :param ifname: str, short form of IOSXR interface name
    :returns: Expanded version of short form interface name
    :rtype: str
    """

    ifmap = {'Ap': 'AppGigabitEthernet',
             'BE': 'Bundle-Ether',
             'BV': 'BVI',
             'Eth': 'Ethernet',
             'Fas': 'FastEthernet',
             'Fa': 'FastEthernet',
             'Fi': 'FiftyGigE',
             'Fo': 'FortyGigE',
             'FH': 'FourHundredGigE',
             'Gi': 'GigabitEthernet',
             'Gig': 'GigabitEthernet',
             'Hu': 'HundredGigE',
             'Lo': 'Loopback',
             'Mg': 'MgmtEth',
             'Nu': 'Null',
             'Po': 'Port-channel',
             'TE': 'TenGigE',
             'Te': 'TenGigabitEthernet',
             'Ten': 'TenGigabitEthernet',
             'TF': 'TwentyFiveGigE',
             'TH': 'TwoHundredGigE',
             'Two': 'TwoGigabitEthernet',
             'Tw': 'TwoGigabitEthernet',
             'tsec': 'tunnel-ipsec',
             'tmte': 'tunnel-mte',
             'tt': 'tunnel-te',
             'tp': 'tunnel-tp',
             'Vl': 'Vlan',
             'CPU': 'cpu',
             }
    pfx = re.match(r'[a-zA-Z]+', ifname)
    if pfx:
        pfxstr = pfx.group(0)
        if pfxstr in ifmap:
            return ifname.replace(pfxstr, ifmap[pfxstr])

    return ifname


def get_sq_install_dir() -> str:
    '''Return the absolute path of the suzieq installation dir'''
    spec = find_spec('suzieq')
    if spec:
        return os.path.dirname(spec.loader.path)
    else:
        return os.path.abspath('./')


def get_sleep_time(period: str) -> int:
    """Returns the duration in seconds to sleep given a period

    Checking if the period format matches a specified format MUST be
    done by the caller.

    :param period: str, the period of form <value><unit>, '15m', '1h' etc
    :returns: duration to sleep in seconds
    :rtype: int
    """
    _, unit, _ = re.split(r'(\D)', period)
    now = datetime.now()
    nextrun = parse(period, settings={'PREFER_DATES_FROM': 'future'})
    if unit == 'm':
        nextrun = nextrun.replace(second=0)
    elif unit == 'h':
        nextrun = nextrun.replace(minute=0, second=0)
    else:
        nextrun = nextrun.replace(hour=0, minute=0, second=0)

    return (nextrun-now).seconds


def convert_asndot_to_asn(asn: str) -> int:
    """Convert BGP ASN into asdot format

    Convert BGP ASN if a single integer to asdot(<asn_hi>.<asn_lo>)
    format. If input ASN is in asdot format already, it returns it as is.
    If input ASN is < 65535, returns it as is.

    Args:
        asn: ASN to convert

    Returns:
        BGP ASN as 32b integer
    """

    if isinstance(asn, int) or '.' not in asn:
        return asn

    s_asn = asn.split('.')
    return int(s_asn[0])*65536+int(s_asn[1])


def print_version():
    '''Print the suzieq version and return'''
    print(SUZIEQ_VERSION)


def deprecated_table_function_warning(dep_table: str, dep_command: str,
                                      table: str = None,
                                      command: str = None) -> str:
    """Return the string of the warning for a deprecated function

    If both table and command aren't provided, the warning will only
    return that the function is deprecated.
    If instead we provide them, the warning will also contain the new command
    to call

    Args:
        table (str): correct table to run the command
        command (str): correct command to call
        dep_table (str): deprecated table command
        dep_command (str): deprecated command
    """
    warning_str = f"WARNING: '{dep_table} {dep_command}' is deprecated."
    if dep_table and dep_command:
        warning_str += f" Use '{table} {command}' instead."
    return warning_str


def deprecated_command_warning(dep_command: str, dep_sub_command: str,
                               command: str = None,
                               sub_command: str = None) -> str:
    """It's a wrapper for the deprecated_table_function_warning. It is used to
    display a message when the user writes a deprecated command.

    Args:
        dep_command (str): deprecated command
        dep_sub_command (str): deprecated sub command
        command (str, optional): command to use instead. Defaults to None.
        sub_command (str, optional): subcommand to use instead.
        Defaults to None.

    Returns:
        str: deprecated command warning message
    """

    return deprecated_table_function_warning(dep_command, dep_sub_command,
                                             command, sub_command)
