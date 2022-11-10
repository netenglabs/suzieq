import asyncio
import copy
import json
import logging
import operator
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from tempfile import mkstemp
from typing import Dict, List, Tuple

import pyarrow as pa
import yaml
from packaging import version as version_parse

from suzieq.poller.worker.services.svcparser \
    import cons_recs_from_json_template
from suzieq.shared.sq_plugin import SqPlugin
from suzieq.shared.utils import get_default_per_vals, known_devtypes
from suzieq.version import SUZIEQ_VERSION

# How long b4 declaring node dead
HOLD_TIME_IN_MSECS = 60000
# How many unsuccessful polls before marking records with active=false
HYSTERESIS_FAILURE_CNT = 3
# The boot timestamp time drift tolerance (in seconds)
TIME_DRIFT_TOLERANCE = 30


@dataclass
class RsltToken:
    '''Cookie passed between service and node objects'''
    start_time: int    # When this cmd was first posted to node
    nodename: str      # Name of node, used to get poller cb again
    bootupTimestamp: int
    nodeQsize: int        # Size of the node q at queuing time
    service: str          # Name of this service, if node needs it
    timeout: int          # timeout value for cmd to complete


@dataclass
class ServiceStats:
    '''Capture useful stats about service'''
    total_time: List[float] = field(default_factory=list)
    gather_time: List[float] = field(default_factory=list)
    svcQsize: List[float] = field(default_factory=list)
    nodeQsize: List[float] = field(default_factory=list)
    wrQsize: List[float] = field(default_factory=list)
    rxBytes: List[float] = field(default_factory=list)
    empty_count: int = 0
    time_excd_count: int = 0    # Number of times total_time > poll period
    next_update_time: int = 0   # When results will be logged


class Service(SqPlugin):
    '''Main class for handling various services/tables processing on devices'''

    def get_poller_schema(self):
        '''Return the schema used by this service'''
        return self._poller_schema

    def set_poller_schema(self, value: dict):
        '''Set the poller schema used by this service'''
        self._poller_schema = value

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, db_access, run_once=None):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields or []
        self.writer_queue = queue
        self.keys = keys
        self.schema = schema.get_arrow_schema()
        self.schema_table = schema
        self.period = period
        self.stype = stype
        self.logger = logging.getLogger(__name__)
        self.run_once = run_once
        self.post_timeout = 5
        self.sigend = False
        self.version = schema.version
        # Get sqobject to retrieve the data of this service
        self._db_access = db_access

        self.update_nodes = False  # we have a new node list
        self.rebuild_nodelist = False  # used only when a node gets init
        self.node_postcall_list = {}
        self.new_node_postcall_list = {}
        self.previous_results = {}
        self._node_boot_timestamps = {}  # dictionary useful to detect reboots
        self._poller_schema = {}
        self.node_boot_times = defaultdict(int)
        self._failed_node_set = set()
        self._consecutive_failures = defaultdict(int)

        self.poller_schema = property(
            self.get_poller_schema, self.set_poller_schema)
        self.poller_schema_version = None

        # The queue to which all nodes will post the result of the command
        self.result_queue = asyncio.Queue()

        # Add the hidden fields to ignore_fields
        self.ignore_fields += ['timestamp', 'sqvers', 'deviceSession']

        if "namespace" not in self.keys:
            self.keys.insert(0, "namespace")

        if "hostname" not in self.keys:
            self.keys.insert(1, "hostname")

        self.partition_cols = schema.get_partition_columns()

        # Setup dictionary of NOS specific extracted data cleaners
        self.dev_clean_fn = {}
        common_dev_clean_fn = getattr(self, '_common_data_cleaner', None)
        for x in known_devtypes():
            if x.startswith('junos'):
                dev = 'junos'
            else:
                dev = x
            self.dev_clean_fn[x] = getattr(
                self, f'_clean_{dev}_data', None) or common_dev_clean_fn

    @ staticmethod
    def is_status_ok(status: int) -> bool:
        '''Did the node return a successful command output'''
        if status in [0, HTTPStatus.OK]:
            return True
        return False

    def get_data(self):
        """provide the data that is interesting for a service

        does not include queue or schema"""

        r = {}
        for fld in ('name defn ignore_fields keys period stype '
                    'partition_cols').split(' '):
            r[field] = getattr(self, fld)
        # textFSM objects can't be jsoned, so changing it
        for device in r['defn']:
            if 'textfsm' in r['defn'][device]:
                r['defn'][device]['textfsm'] = str(
                    r['defn'][device]['textfsm'])
        return r

    async def set_nodes(self, node_call_list):
        """New node list for this service"""
        if self.node_postcall_list:
            self.new_node_postcall_list = node_call_list
            self.update_nodes = True
        else:
            self.node_postcall_list = node_call_list

    def get_empty_record(self):
        '''Return an empty record matching schema'''
        map_defaults = get_default_per_vals()

        defaults = [map_defaults[x] for x in self.schema.types]
        rec = dict(zip(self.schema.names, defaults))

        return rec

    def _dump_output(self, outputs) -> str:
        """Dump the output to a YAML file"""
        if outputs:
            yml = {"service": self.name,
                   "type": self.run_once,
                   "output": outputs}
            fd, name = mkstemp(suffix=f"-{self.name}-poller.yml")
            f = os.fdopen(fd, "w")
            f.write(yaml.dump(yml))
            f.close()
            return name
        return ""

    def get_diff(self, old: List[Dict], new: List[Dict],
                 add_all: bool) -> Tuple[List, List]:
        """Get the difference between the old and the new result

        Args:
            old (List[Dict]): previous result
            new (List[Dict]): new result
            add_all (bool): if True return all the records in adds, even though
                nothing changed.

        Returns:
            Tuple[List, List]: return additions and deletions to respect the
                previous result.
        """
        # If old is empty there is no need to look for differences
        # just return adds
        if not old:
            return new, []

        # Work out the differences between the new and the old records
        adds = []
        dels = []
        koldvals = []
        knewvals = []
        koldkeys = []
        knewkeys = []

        fieldsToCheck = set()
        # keys that start with _ are transient and must be ignored
        # from comparison
        for elem in new:
            # Checking the __iter__ attribute to check if it is iterable
            # is not pythonic but much faster, we need to be fast since this
            # piece of code is executed tons of times
            vals = {k: set(v) if hasattr(v, '__iter__') and
                    not isinstance(v, str) and
                    not isinstance(v, dict) else str(v)
                    for k, v in elem.items()
                    if k not in self.ignore_fields and not k.startswith('_')
                    and k in self.schema_table.fields}
            kvals = {v for k, v in elem.items() if k in self.keys}
            knewvals.append(vals)
            knewkeys.append(kvals)
            fieldsToCheck.update(vals.keys())

        for elem in old:
            # Get from the old records only the fields there are in new records
            # since we want to compare what we have, also excluding all the
            # derived derived colums, which are not explicitly written in
            # the data.
            vals = {k: set(v) if hasattr(v, '__iter__') and
                    not isinstance(v, str) and
                    not isinstance(v, dict) else str(v)
                    for k, v in elem.items()
                    if k in fieldsToCheck}
            kvals = {v for k, v in elem.items() if k in self.keys}
            koldvals.append(vals)
            koldkeys.append(kvals)

        if add_all or self.stype == 'counters':
            adds = new
        else:
            adds = [new[k]
                    for k, v in enumerate(knewvals)
                    if v not in koldvals]
        dels = [old[k] for k, v in enumerate(koldvals)
                if v not in knewvals and koldkeys[k] not in knewkeys]

        # The sqvers type for dels might be float, we expect str
        for d in dels:
            if d.get('sqvers'):
                d['sqvers'] = str(d['sqvers'])

        return adds, dels

    def textfsm_data(self, raw_input, fsm_template, entry_type, _1, _2):
        """Convert unstructured output to structured output"""

        records = []
        fsm_template.Reset()
        res = fsm_template.ParseText(raw_input)

        for entry in res:
            metent = dict(zip(fsm_template.header, entry))
            if entry_type:
                metent['_entryType'] = entry_type
            records.append(metent)

        return records

    async def post_results(self, result, token) -> None:
        """Callback fn used to post the results back to the service"""
        if self.result_queue:
            self.result_queue.put_nowait((token, result))
        else:
            self.logger.error(f"No queue for service {self.name}")

    def call_node_postcmd(self, postcall, nodename) -> None:
        """Start data gathering by calling the post command list"""
        if postcall and postcall['postq']:
            token = RsltToken(int(time.time()*1000), nodename, 0, 0, self.name,
                              self.period-5)
            postcall['postq'](self.post_results, self.defn, token)

    def clean_json_input(self, data):
        """Clean the JSON input data that is sometimes messed up
        Each service can implement its own version of the cleanup
        """
        return data.get('data', {})

    async def start_data_gather(self) -> None:
        """Start data gathering by calling the post command list
        This is only used to fire up the calls the first time. After this,
        each node gets into a self-adapting curve of calling at least after
        the duration specified for the service period. If nodes are slower,
        they'll be scheduled to run after the specified service period after
        their return. We could use this to track slow nodes.
        """

        for node in self.node_postcall_list:
            try:
                self.call_node_postcmd(self.node_postcall_list[node],
                                       node),
            except TimeoutError:
                self.logger.warning(f"Node post failed for {node}")
                continue

    def _get_def_for_version(self, defn: List, version: str) -> Dict:
        '''Extract the right definition for the version'''
        if isinstance(defn, dict):
            return defn

        if not isinstance(defn, list):
            return defn

        for item in defn:
            os_version = item.get('version', '')
            if os_version == "all":
                return item
            if version == 0:
                # There are various outputs that due to an old parsing bug
                # return a node version of 0. Use 'all' for those
                continue
            opdict = {'>': operator.gt, '<': operator.lt,
                      '>=': operator.ge, '<=': operator.le,
                      '=': operator.eq, '!=': operator.ne}
            op = operator.eq

            for elem, val in opdict.items():
                if os_version.startswith(elem):
                    os_version = os_version.replace(
                        elem, '').strip()
                    op = val
                    break

            if op(version_parse.LegacyVersion(version),
                  version_parse.LegacyVersion(os_version)):
                return item

        return None

    def _get_device_normalizer(self, data: Dict) -> Dict:
        '''Returns the normalizer string appropriate for the data

        Every NOS/version has a normalizer string specified in the
        service config file (under suzieq/config). This function
        returns that string for the given data input
        '''
        nfn = self.defn.get(data.get("hostname"), {})
        if not nfn:
            nfn = self.defn.get(data.get("devtype"), {})
        if nfn:
            # If we're riding on the coattails of another device
            # get that device's normalization function
            if isinstance(nfn, dict):
                copynfn = nfn.get("copy", {})
                if copynfn:
                    nfn = self.defn.get(copynfn, {})
            if isinstance(nfn, list):
                nfn = self._get_def_for_version(nfn, data.get("version"))

        return nfn

    def _process_each_output(self, elem_num, data, nfn):
        """Workhorse processing routine for each element in output"""

        result = []
        if (Service.is_status_ok(data.get('status', -1))):
            if not data["data"]:
                return result

            # Check host-specific normalization if any
            if nfn:
                norm_str = nfn.get("normalize", None)
                if norm_str is None and isinstance(nfn.get('command', None),
                                                   list):
                    # Can happen because we've a list of commands associated
                    # Pick the normalization function associated with this
                    # output
                    norm_str = nfn.get('command', [])[elem_num].get(
                        'normalize', None)
                if norm_str:
                    if isinstance(data["data"], str):
                        try:
                            in_info = json.loads(data["data"])
                        except json.JSONDecodeError:
                            in_info = self.clean_json_input(data)
                            if not in_info:
                                self.logger.error(
                                    "Received non-JSON output where "
                                    "JSON was expected for %s on "
                                    "node %s, %s",
                                    data["cmd"], data["hostname"],
                                    data["data"]
                                )
                                return result
                            try:
                                in_info = json.loads(in_info)
                            except json.JSONDecodeError:
                                self.logger.error(
                                    "Received non-JSON output where "
                                    "JSON was expected for %s on "
                                    "node %s, %s",
                                    data["cmd"], data["hostname"],
                                    data["data"]
                                )
                                return result
                    else:
                        in_info = data["data"]

                    if in_info:
                        # EOS' HTTP returns errors like this.
                        if isinstance(in_info, dict):
                            tmp = in_info.get('data', [])
                            if tmp and tmp[0].get('errors', {}):
                                return []

                        result = cons_recs_from_json_template(
                            norm_str, in_info)

                else:
                    tfsm_template = nfn.get("textfsm", None)
                    entry_type = None
                    if tfsm_template is None and isinstance(
                            nfn.get('command', None), list):
                        # Can happen because we've a list of cmds associated
                        # Pick the normalization function associated with this
                        # output
                        tfsm_template = nfn.get('command', [])[elem_num].get(
                            'textfsm', None)
                        entry_type = nfn.get('command', [])[elem_num].get(
                            '_entryType', None)
                    else:
                        entry_type = nfn.get('_entryType', None)

                    if not tfsm_template:
                        return result

                    in_info = []
                    if isinstance(data['data'], dict):
                        if "output" in data["data"]:
                            in_info = data["data"]["output"]
                        elif "messages" in data["data"]:
                            # This is Arista's bash output format
                            in_info = data["data"]["messages"][0]
                    else:
                        in_info = data['data']
                    if not in_info:
                        return result  # No data to process
                    # Clean data is invoked inside this due to the way we
                    # munge the data and force the types to adhere to the
                    # specified type
                    result = self.textfsm_data(
                        in_info, tfsm_template, entry_type, self.schema, data
                    )
            else:
                self.logger.error(
                    "%s: No normalization/textfsm function for device %s",
                    self.name, data["hostname"])

        return result

    def process_data(self, data):
        """Derive the data to be stored from the raw input"""
        result_list = []
        do_merge = True
        for i, item in enumerate(data):
            nfn = self._get_device_normalizer(item)
            do_merge = do_merge and nfn and nfn.get('merge', True)
            tmpres = self._process_each_output(i, item, nfn)
            result_list.append(tmpres)

        if do_merge:
            result = self.merge_results(result_list, data)
        else:
            result = [ele for sublist in result_list for ele in sublist]
        return self.clean_data(result, data)

    def get_key_flds(self):
        """Get the key fields associated with this service.
        Its a function because we want to override it.
        """
        return list(filter(lambda x: x not in ['namespace', 'hostname'],
                           self.keys))

    def merge_results(self, result_list, _):
        '''Merge the results from multiple commands into a single result'''

        int_res = {}
        keyflds = self.get_key_flds()

        for result in result_list:
            for entry in result:
                keyvals = []
                for kfld in keyflds:
                    if not entry.get(kfld, None):
                        keyvals.append('_default')
                    else:
                        val = entry.get(kfld, '')
                        if not isinstance(val, str):
                            val = str(val)
                        keyvals.append(val)

                if entry.get('_entryType', ''):
                    keyvals.append(entry['_entryType'])

                key = '-'.join(keyvals)

                if key not in int_res:
                    int_res[key] = entry
                else:
                    existing = int_res[key]
                    for fld in entry:
                        if entry[fld] and not existing.get(fld, None):
                            existing[fld] = entry[fld]
                        elif entry[fld]:
                            # cleanup routine specific to service can resolve
                            existing[fld+"-_2nd"] = entry[fld]

        final_res = list(int_res.values())

        return(final_res)

    def _get_devtype_from_input(self, input_data):
        if isinstance(input_data, list):
            return input_data[0].get('devtype', None)
        else:
            return input_data.get('devtype', None)

    def clean_data(self, processed_data, raw_data):
        """Massage the extracted data to match record specified by schema"""

        dev_clean_fn = self.dev_clean_fn.get(self._get_devtype_from_input(
            raw_data), None)
        if dev_clean_fn:
            processed_data = dev_clean_fn(processed_data, raw_data)

        return self.clean_data_common(processed_data, raw_data)

    def clean_data_common(self, processed_data, raw_data):
        """Fix the type and default value of of each extracted field

        This routine is common to all services. It ensures that all the missing
        fields, as defined by the schema, are added to the records extracted.
        Furthermore, each field is set to the specified type.
        """

        # Build default data structure
        schema_rec = {}
        def_vals = get_default_per_vals()

        ptype_map = {
            pa.string(): str,
            pa.int32(): int,
            pa.int64(): int,
            pa.float32(): float,
            pa.float64(): float,
            pa.date64(): float,
            pa.list_(pa.string()): list,
            pa.list_(pa.int64()): list,
            pa.bool_(): bool,
        }

        for fld in self.schema:
            default = def_vals[fld.type]
            schema_rec.update({fld.name: default})

        if isinstance(raw_data, list):
            read_from = raw_data[0]
        else:
            read_from = raw_data

        # pylint: disable=too-many-nested-blocks
        for entry in processed_data or []:
            entry.update({"hostname": read_from["hostname"]})
            entry.update({"namespace": read_from["namespace"]})
            entry.update({"timestamp": read_from["timestamp"]})
            entry.update({"sqvers": self.version})
            for fld, val in schema_rec.items():
                if fld not in entry:
                    if fld == "active":
                        entry.update({fld: True})
                    else:
                        entry.update({fld: val})
                else:
                    fld_type = self.schema.field(fld).type
                    if not isinstance(entry[fld], ptype_map[fld_type]):
                        try:
                            entry[fld] = ptype_map[fld_type](entry[fld])
                        except (ValueError, TypeError):
                            entry[fld] = val
                    elif isinstance(entry[fld], list):
                        for i, ele in enumerate(entry[fld]):
                            if not isinstance(ele,
                                              ptype_map[fld_type.value_type]):
                                try:
                                    if ptype_map[fld_type.value_type] == int:
                                        entry[fld][i] = int(entry[fld][i])
                                    elif ptype_map[fld_type.value_type] == str:
                                        entry[fld][i] = str(entry[fld][i])
                                    else:
                                        raise ValueError
                                except (ValueError, TypeError):
                                    entry[fld][i] = val
        return processed_data

    async def commit_data(self, result: Dict, namespace: str, hostname: str,
                          boot_timestamp: float):
        """Write the result data out"""
        records = []
        key = f'{namespace}.{hostname}'
        prev_res = self.previous_results.get(key, None)
        last_device_session = self._node_boot_timestamps.get(key, 0)
        # No data previously polled with this service from the the
        # current namespace and hostname. Check if the datastore contains some
        # information about
        filter_df = f"hostname.str.match('{hostname}') and " \
                    f"namespace.str.match('{namespace}')"
        if prev_res is None:
            df = self._db_access.read(
                self.schema_table._table,
                'pandas',
                start_time='',
                end_time='',
                columns=self.schema_table.fields,
                view='latest',
                key_fields=self.schema_table.key_fields(),
                add_filter=filter_df,
                hostname=[hostname],
                namespace=[namespace]).query('active')
            # Get the latest device session we have written with this service
            if not df.empty:
                last_device_session = df['deviceSession'].iloc[0] or 0
                self._node_boot_timestamps[key] = int(last_device_session)

            prev_res = df.to_dict('records')
            self.previous_results[key] = prev_res

        if result or prev_res:
            # Check whether there has been a node reboot and in this case
            # write everything
            write_all = abs(boot_timestamp -
                            last_device_session) > TIME_DRIFT_TOLERANCE
            if write_all:
                last_device_session = int(boot_timestamp)
                self._node_boot_timestamps[key] = boot_timestamp

            adds, dels = self.get_diff(prev_res, result, write_all)
            if adds or dels:
                self.previous_results[key] = copy.deepcopy(result)
                for entry in adds:
                    entry['deviceSession'] = last_device_session
                    records.append(entry)
                for entry in dels:
                    if entry.get("active", True):
                        # If there's already an entry marked as deleted
                        # No point in adding one more
                        entry.update({"active": False})
                        entry.update(
                            {"timestamp":
                             int(datetime.now(tz=timezone.utc).timestamp()
                                 * 1000)}
                        )
                        records.append(entry)

                self._post_work_to_writer(records)

    def _post_work_to_writer(self, records: dict):
        """This posts the data to be written to the worker queue"""
        if records:
            self.writer_queue.put_nowait(
                {
                    "records": records,
                    "topic": self.name,
                    "schema": self.schema,
                    "partition_cols": self.partition_cols
                }
            )

    def reset_stats(self, stats: ServiceStats) -> None:
        """Reset the stats arrays.
        """
        stats.total_time = []
        stats.gather_time = []
        stats.svcQsize = []
        stats.nodeQsize = []
        stats.wrQsize = []
        stats.rxBytes = []
        stats.empty_count = 0
        stats.time_excd_count = 0

    def compute_basic_stats(self, statsList, newval: int) -> None:
        """Compute min/max/avg for given stats with the new value

        :param statsList: list consisting of 3 values in order: min, max, avg
        :type statsList: list_

        :param newval: The newval to update the list with
        :type newval: int
        """
        if not statsList:
            statsList = [newval, newval, newval]
            return statsList

        if newval < statsList[0]:
            statsList[0] = newval
        if newval > statsList[1]:
            statsList[1] = newval
        statsList[2] = (statsList[2]+newval)/2
        if statsList[2] < 0.001:
            statsList[2] = 0

        return statsList

    def update_stats(self, stats: ServiceStats, total_time: int,
                     gather_time: int, qsize: int, wrQsize: int,
                     nodeQsize: int, rxBytes) -> bool:
        """Update per-node stats"""
        write_stat = False
        now = int(time.time()*1000)

        stats.total_time = self.compute_basic_stats(stats.total_time,
                                                    total_time)
        stats.gather_time = self.compute_basic_stats(stats.gather_time,
                                                     gather_time)
        stats.svcQsize = self.compute_basic_stats(stats.svcQsize, qsize)
        stats.wrQsize = self.compute_basic_stats(stats.wrQsize, wrQsize)
        stats.nodeQsize = self.compute_basic_stats(stats.nodeQsize, nodeQsize)
        stats.rxBytes = self.compute_basic_stats(stats.rxBytes, rxBytes)

        if total_time > self.period*1000:
            stats.time_excd_count += 1
            write_stat = True

        if now > stats.next_update_time:
            stats.next_update_time = now + 5*60*1000  # 5 mins
            write_stat = True

        return write_stat

    def is_first_run(self, key: str) -> bool:
        '''Boolean indicating wether the current run
           is the first since the service is running.
        '''
        return not self.previous_results.get(key, None)

    # pylint: disable=too-many-statements
    async def run(self):
        """Start the service"""
        self.logger.info(f"running service {self.name} ")

        if self.run_once:
            total_nodes = len(self.node_postcall_list)
        else:
            total_nodes = 0
        # Fire up the initial posts
        await self.start_data_gather()
        loop = asyncio.get_running_loop()
        # pylint: disable=unnecessary-lambda
        pernode_stats = defaultdict(lambda: ServiceStats())

        while True:
            try:
                token, output = await self.result_queue.get()
            except asyncio.CancelledError:
                self.logger.warning(
                    f'Service: {self.name}: Received signal to terminate')
                return
            qsize = self.result_queue.qsize()

            self.logger.debug(f"Extracted response for {self.name} service")
            if isinstance(token, list):
                token = token[0]
            gather_time = int(time.time()*1000) - token.start_time

            status = HTTPStatus.NO_CONTENT        # Empty content
            write_poller_stat = False
            rxBytes = 0

            if output:
                ostatus = [x.get('status', -1) for x in output]

                should_commit = True

                # we should always commit during the first run of the service
                # for each node regardless their status.
                if not self.is_first_run(token.nodename):
                    # If it's not the first run and some command did fail,
                    # increment the count to be used in hysteresis.
                    # The info will be committed in a future run.
                    if any((not Service.is_status_ok(x) for x in ostatus)):
                        self._consecutive_failures[token.nodename] += 1
                    # otherwise reset the counter.
                    else:
                        self._consecutive_failures[token.nodename] = 0

                if 0 < self._consecutive_failures[token.nodename] < \
                        HYSTERESIS_FAILURE_CNT:
                    self.logger.info(
                        f"{self.name} {token.nodename} node failure hysteresis"
                        ", skipping data commit")
                    should_commit = False

                # pylint: disable=use-a-generator
                write_poller_stat = not all([Service.is_status_ok(x)
                                             for x in ostatus])
                status = ostatus[0]
                if (status in [0, 200]):
                    rxBytes = len(str(output))

                # We don't expect the output from two different hostnames
                nodename = output[0]["hostname"]
                self.logger.debug(f"Extracted response from {nodename} for "
                                  f"{self.name} service")
                # We can terminate processing if we've no data returned
                # and we're reading inputs from a file
                if nodename == '_filedata' and status == HTTPStatus.NO_CONTENT:
                    return

                # Process data independent of status to return an empty list
                # so that the output can be updated. For example, if a service
                #  is disabled, this can be the condition.
                if self.run_once == "gather":
                    if self.is_status_ok(status):
                        self._post_work_to_writer(json.dumps(output, indent=4))
                    total_nodes -= 1
                    if total_nodes <= 0:
                        self.logger.warning(
                            f'Service: {self.name}: Finished gathering data')
                        return
                    continue

                try:
                    result = self.process_data(output)
                except Exception:  # pylint: disable=broad-except
                    result = []
                    status = HTTPStatus.BAD_GATEWAY
                    write_poller_stat = True
                    self.logger.exception(
                        f'Processing data failed for service '
                        f'{self.name} on node {nodename}')

                # Don't write the error every time the failure happens
                if write_poller_stat:
                    if nodename in self._failed_node_set:
                        write_poller_stat = False
                    else:
                        self._failed_node_set.add(nodename)
                elif nodename in self._failed_node_set:
                    # So there was no error in this command that had failed b4
                    self._failed_node_set.remove(nodename)

                # If a node from init state to good state, hostname will change
                # So fix that in the node list
                if self.run_once == "process":
                    if self.is_status_ok(status):
                        self._post_work_to_writer(json.dumps(result, indent=4))
                    total_nodes -= 1
                    if total_nodes <= 0:
                        return
                    continue

                if should_commit:
                    await self.commit_data(result, output[0]["namespace"],
                                           output[0]["hostname"],
                                           token.bootupTimestamp)
            elif self.run_once in ["gather", "process", "update"]:
                total_nodes -= 1
                if total_nodes <= 0:
                    self.logger.info(f'Service: {self.name}: Finished '
                                     f'{self.run_once}ing data')
                    return
                continue

            total_time = int(time.time()*1000) - token.start_time

            if output:

                stats = pernode_stats[token.nodename]
                write_poller_stat = (self.update_stats(
                    stats, total_time, gather_time, qsize,
                    self.writer_queue.qsize(), token.nodeQsize, rxBytes) or
                    write_poller_stat or
                    self.is_first_run(token.nodename))
                pernode_stats[token.nodename] = stats
                if write_poller_stat:
                    poller_stat = [
                        {"hostname": (output[0]["hostname"] or
                                      output[0]['address']),
                         "sqvers": self.poller_schema_version,
                         "namespace": output[0]["namespace"],
                         "active": True,
                         "service": self.name,
                         "status": status,
                         "svcQsize": stats.svcQsize,
                         "wrQsize": stats.wrQsize,
                         "nodeQsize": stats.nodeQsize,
                         "rxBytes": stats.rxBytes,
                         "pollExcdPeriodCount": stats.time_excd_count,
                         "gatherTime": stats.gather_time,
                         "totalTime": stats.total_time,
                         "version": SUZIEQ_VERSION,
                         "nodesPolledCnt": len(self.node_postcall_list),
                         "nodesFailedCnt": len(self._failed_node_set),
                         "timestamp": int(datetime.now(tz=timezone.utc)
                                          .timestamp() * 1000)}]

                    self.writer_queue.put_nowait(
                        {
                            "records": poller_stat,
                            "topic": "sqPoller",
                            "schema": self.poller_schema,
                            "partition_cols": self.partition_cols
                        })
                    self.reset_stats(pernode_stats[token.nodename])

            # Post a cmd to fire up the next poll after the specified period
            if self.run_once == "update":
                total_nodes -= 1
                if total_nodes <= 0:
                    self.logger.info(
                        f'Service: {self.name}: Finished updating data')
                    return
                continue
            self.logger.debug(
                f"Rescheduling service for {self.name} service")
            loop.call_later(self.period, self.call_node_postcmd,
                            self.node_postcall_list.get(token.nodename),
                            token.nodename)
