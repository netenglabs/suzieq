import os
import sys
import asyncio
from datetime import datetime
import time
import copy
import logging
import json
import yaml
from tempfile import mkstemp
from dataclasses import dataclass
from http import HTTPStatus
from collections import defaultdict

import pyarrow as pa

from suzieq.poller.services.svcparser import cons_recs_from_json_template
from suzieq.utils import calc_avg

HOLD_TIME_IN_MSECS = 60000  # How long b4 declaring node dead


@dataclass
class RsltToken:
    start_time: int    # When this cmd was first posted to node
    nodename: str      # Name of node, used to get poller cb again
    bootupTimestamp: int
    nodeQsize: int        # Size of the node q at queuing time
    service: str          # Name of this service, if node needs it


@dataclass
class ServiceStats:
    min_svc_time: int = 0
    max_svc_time: int = 0
    avg_svc_time: float = 0.0
    max_gather_time: int = 0
    min_gather_time: int = 0
    avg_gather_time: float = 0.0
    empty_count: int = 0
    min_qsize: int = 0
    max_qsize: int = 0
    avg_qsize: float = 0.0      # service queue size
    min_wrQsize: int = 0
    max_wrQsize: int = 0
    avg_wrQsize: float = 0.0    # write queue size
    min_nodeQsize: int = 0
    max_nodeQsize: int = 0
    avg_nodeQsize: float = 0.0
    time_excd_count: int = 0    # Number of times total_time > poll period
    next_update_time: int = 0   # When results will be logged


class Service(object):

    def get_poller_schema(self):
        return self._poller_schema

    def set_poller_schema(self, value: dict):
        self._poller_schema = value

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields or []
        self.writer_queue = queue
        self.keys = keys
        self.schema = schema
        self.period = period
        self.stype = stype
        self.logger = logging.getLogger("suzieq")
        self.run_once = run_once
        self.post_timeout = 5

        self.update_nodes = False  # we have a new node list
        self.rebuild_nodelist = False  # used only when a node gets init
        self.node_postcall_list = {}
        self.new_node_postcall_list = {}
        self.previous_results = {}
        self._poller_schema = {}
        self.node_boot_times = defaultdict(int)

        self.poller_schema = property(
            self.get_poller_schema, self.set_poller_schema)

        # The queue to which all nodes will post the result of the command
        self.result_queue = asyncio.Queue()

        # Add the hidden fields to ignore_fields
        self.ignore_fields.append("timestamp")

        if "namespace" not in self.keys:
            self.keys.insert(0, "namespace")

        if "hostname" not in self.keys:
            self.keys.insert(1, "hostname")

        if self.stype == "counters":
            self.partition_cols = ["namespace", "hostname"]
        else:
            self.partition_cols = self.keys + ["timestamp"]

    def is_status_ok(self, status: int) -> bool:
        if status == 0 or status == HTTPStatus.OK:
            return True
        return False

    def get_data(self):
        """provide the data that is interesting for a service

        does not include queue or schema"""

        r = {}
        for field in 'name defn ignore_fields keys period stype partition_cols'.split(' '):
            r[field] = getattr(self, field)
        # textFSM objects can't be jsoned, so changing it
        for device in r['defn']:
            if 'textfsm' in r['defn'][device]:
                r['defn'][device]['textfsm'] = str(
                    r['defn'][device]['textfsm'])
        return r

    def set_nodes(self, node_call_list):
        """New node list for this service"""
        if self.node_postcall_list:
            self.new_node_postcall_list = node_call_list
            self.update_nodes = True
        else:
            self.node_postcall_list = node_call_list

    def get_empty_record(self):
        map_defaults = {
            pa.string(): "",
            pa.int32(): 0,
            pa.int64(): 0,
            pa.float32(): 0.0,
            pa.float64(): 0.0,
            pa.date64(): 0.0,
            pa.bool_(): False,
            pa.list_(pa.string()): [],
            pa.list_(pa.int64()): [],
        }

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

    def get_diff(self, old, new):
        """Compare list of dictionaries ignoring certain fields
        Return list of adds and deletes
        """
        adds = []
        dels = []
        koldvals = {}
        knewvals = {}
        koldkeys = []
        knewkeys = []

        for i, elem in enumerate(old):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            kvals = [v for k, v in elem.items() if k in self.keys]
            koldvals.update({tuple(str(vals)): i})
            koldkeys.append(kvals)

        for i, elem in enumerate(new):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            kvals = [v for k, v in elem.items() if k in self.keys]
            knewvals.update({tuple(str(vals)): i})
            knewkeys.append(kvals)

        addlist = [v for k, v in knewvals.items() if k not in koldvals.keys()]
        dellist = [v for k, v in koldvals.items() if k not in knewvals.keys()]

        adds = [new[v] for v in addlist]
        dels = [old[v] for v in dellist if koldkeys[v] not in knewkeys]

        if adds and self.stype == "counters":
            # If there's a change in any field of the counters, update them all
            # simplifies querying
            adds = new

        return adds, dels

    def textfsm_data(self, raw_input, fsm_template, schema, data):
        """Convert unstructured output to structured output"""

        records = []
        fsm_template.Reset()
        res = fsm_template.ParseText(raw_input)

        for entry in res:
            metent = dict(zip(fsm_template.header, entry))
            records.append(metent)

        result = self.clean_data(records, data)

        fields = [fld.name for fld in schema]

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
            pa.list_(pa.struct([('nexthop', pa.string()),
                                ('oif', pa.string()),
                                ('weight', pa.int32())])): list,
        }

        map_defaults = {
            pa.string(): "",
            pa.int32(): 0,
            pa.int64(): 0,
            pa.float32(): 0.0,
            pa.float64(): 0.0,
            pa.date64(): 0.0,
            pa.bool_(): False,
            pa.list_(pa.string()): [],
            pa.list_(pa.int64()): [],
            pa.list_(pa.struct([('nexthop', pa.string()),
                                ('oif', pa.string()),
                                ('weight', pa.int32())])): [("", "", 1)]
        }

        # Ensure the type is set correctly.
        for entry in result:
            for cent in entry:
                if cent in fields:
                    schent_type = schema.field(cent).type
                    if not isinstance(entry[cent], ptype_map[schent_type]):
                        if entry[cent]:
                            entry[cent] = ptype_map[schent_type](entry[cent])
                        else:
                            entry[cent] = map_defaults[schent_type]
                    elif isinstance(entry[cent], list):
                        for i, ele in enumerate(entry[cent]):
                            if not isinstance(ele, ptype_map[schent_type.value_type]):
                                try:
                                    if ptype_map[schent_type.value_type] == int:
                                        entry[cent][i] = int(entry[cent][i])
                                    else:
                                        raise ValueError
                                except ValueError:
                                    entry[cent][i] = (
                                        map_defaults[schent_type.value_type])

        return result

    async def post_results(self, result, token) -> None:
        """The callback that nodes use to post the results back to the service"""
        if self.result_queue:
            self.result_queue.put_nowait((token, result))
        else:
            self.logger.error(f"No queue for service {self.name}")

    def call_node_postcmd(self, postcall, nodename) -> None:
        """Start data gathering by calling the post command list"""
        if postcall and postcall['postq']:
            token = RsltToken(int(time.time()*1000), nodename, 0, 0, self.name)
            postcall['postq'](self.post_results, self.defn, token)

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

    def process_data(self, data):
        """Derive the data to be stored from the raw input"""
        result = []

        if (data["status"] is not None) and (int(data["status"]) == 200 or
                                             int(data["status"]) == 0):
            if not data["data"]:
                return result

            nfn = self.defn.get(data.get("hostname"), None)
            if not nfn:
                nfn = self.defn.get(data.get("devtype"), None)
            if nfn:
                copynfn = nfn.get("copy", None)
                if copynfn:
                    nfn = self.defn.get(copynfn, {})
                if nfn.get("normalize", None):
                    if isinstance(data["data"], str):
                        try:
                            in_info = json.loads(data["data"])
                        except json.JSONDecodeError:
                            self.logger.error(
                                "Received non-JSON output where "
                                "JSON was expected for {} on "
                                "node {}, {}".format(
                                    data["cmd"], data["hostname"], data["data"]
                                )
                            )
                            return result
                    else:
                        in_info = data["data"]

                    if in_info:
                        # EOS' HTTP returns errors like this.
                        tmp = in_info.get('data', [])
                        if tmp and tmp[0].get('errors', {}):
                            return []

                        result = cons_recs_from_json_template(
                            nfn.get("normalize", ""), in_info)

                        result = self.clean_data(result, data)
                else:
                    tfsm_template = nfn.get("textfsm", None)
                    if not tfsm_template:
                        return result

                    if "output" in data["data"]:
                        in_info = data["data"]["output"]
                    elif "messages" in data["data"]:
                        # This is Arista's bash output format
                        in_info = data["data"]["messages"][0]
                    else:
                        in_info = data["data"]
                    # Clean data is invoked inside this due to the way we
                    # munge the data and force the types to adhere to the
                    # specified type
                    result = self.textfsm_data(
                        in_info, tfsm_template, self.schema, data
                    )
            else:
                self.logger.error(
                    "{}: No normalization/textfsm function for device {}"
                    .format(self.name, data["hostname"]))

        return result

    def clean_data(self, processed_data, raw_data):

        # Build default data structure
        schema_rec = {}
        def_vals = {
            pa.string(): "-",
            pa.int32(): 0,
            pa.int64(): 0,
            pa.float64(): 0,
            pa.float32(): 0.0,
            pa.bool_(): False,
            pa.date64(): 0.0,
            pa.list_(pa.string()): ["-"],
            pa.list_(pa.int64()): [0],
            pa.list_(pa.struct([('nexthop', pa.string()),
                                ('oif', pa.string()),
                                ('weight', pa.int32())])): [("", "", 1)],
        }
        for field in self.schema:
            default = def_vals[field.type]
            schema_rec.update({field.name: default})

        for entry in processed_data:
            entry.update({"hostname": raw_data["hostname"]})
            entry.update({"namespace": raw_data["namespace"]})
            entry.update({"timestamp": raw_data["timestamp"]})
            for fld in schema_rec:
                if fld not in entry:
                    if fld == "active":
                        entry.update({fld: True})
                    else:
                        entry.update({fld: schema_rec[fld]})

        return processed_data

    async def commit_data(self, result, namespace, hostname):
        """Write the result data out"""
        records = []
        prev_res = self.previous_results.get(hostname, [])

        if result or prev_res:
            adds, dels = self.get_diff(prev_res, result)
            if adds or dels:
                self.previous_results[hostname] = copy.deepcopy(result)
                for entry in adds:
                    records.append(entry)
                for entry in dels:
                    if entry.get("active", True):
                        # If there's already an entry marked as deleted
                        # No point in adding one more
                        entry.update({"active": False})
                        entry.update(
                            {"timestamp":
                             int(datetime.utcnow().timestamp() * 1000)}
                        )
                        records.append(entry)

            if records:
                self.writer_queue.put_nowait(
                    {
                        "records": records,
                        "topic": self.name,
                        "schema": self.schema,
                        "partition_cols": self.partition_cols,
                    }
                )

    def update_stats(self, stats: ServiceStats, gather_time: int,
                     total_time: int, qsize: int, wrQsize: int,
                     nodeQsize: int) -> bool:
        """Update per-node stats"""
        write_stat = False
        now = int(time.time()*1000)
        if total_time < stats.min_svc_time:
            stats.min_svc_time = total_time
        if total_time > stats.max_svc_time:
            stats.max_svc_time = total_time
        stats.avg_svc_time = calc_avg(stats.avg_svc_time, total_time)
        stats.avg_gather_time = calc_avg(stats.avg_gather_time, gather_time)
        stats.avg_qsize = calc_avg(stats.avg_qsize, qsize)
        stats.avg_wrQsize = calc_avg(stats.avg_wrQsize, wrQsize)
        stats.avg_nodeQsize = calc_avg(stats.avg_nodeQsize, nodeQsize)

        if total_time > self.period*1000:
            stats.time_excd_count += 1
            write_stat = True

        if now > stats.next_update_time:
            stats.next_update_time = now + 5*60*1000  # 5 mins
            write_stat = True

        return write_stat

    async def run(self):
        """Start the service"""
        self.logger.info(f"running service {self.name} ")

        # Fire up the initial posts
        await self.start_data_gather()
        loop = asyncio.get_running_loop()
        pernode_stats = defaultdict(lambda: ServiceStats())

        while True:
            token, output = await self.result_queue.get()
            qsize = self.result_queue.qsize()

            self.logger.debug(f"Extracted response for {self.name} service")
            if isinstance(token, list):
                token = token[0]
            gather_time = int(time.time()*1000) - token.start_time

            status = HTTPStatus.NO_CONTENT        # Empty content
            write_poller_stat = False

            if output:
                ostatus = output[0].get("status", None)
                if ostatus is not None:
                    try:
                        status = int(ostatus)
                    except ValueError:
                        status = HTTPStatus.METHOD_NOT_ALLOWED

                write_poller_stat = not self.is_status_ok(status)
                result = self.process_data(output[0])
                # If a node from init state to good state, hostname will change
                # So fix that in the node list
                hostname = output[0]["hostname"]
                if token.bootupTimestamp != self.node_boot_times[hostname]:
                    self.node_boot_times[hostname] = token.bootupTimestamp
                    # Flush the prev results data for this node
                    self.previous_results[hostname] = []
                await self.commit_data(result, output[0]["namespace"], hostname)
                empty_count = False
            else:
                empty_count = True

            total_time = int(time.time()*1000) - token.start_time

            if not empty_count:
                statskey = output[0]["namespace"] + '/' + output[0]["hostname"]
                write_poller_stat = (write_poller_stat or
                                     self.update_stats(
                                         pernode_stats[statskey], total_time,
                                         gather_time, qsize,
                                         self.writer_queue.qsize(),
                                         token.nodeQsize))
                stats = pernode_stats[statskey]
                poller_stat = [
                    {"hostname": output[0]["hostname"],
                     "namespace": output[0]["namespace"],
                     "active": True,
                     "service": self.name,
                     "status": status,
                     "svcQsize": stats.avg_qsize,
                     "wrQsize": stats.avg_wrQsize,
                     "nodeQsize": stats.avg_nodeQsize,
                     "pollExcdPeriodCount": stats.time_excd_count,
                     "gatherTime": stats.avg_gather_time,
                     "totalTime": stats.avg_svc_time,
                     "emptyCount": empty_count,
                     "timestamp": int(datetime.utcnow().timestamp() * 1000)}]

            if write_poller_stat:
                self.writer_queue.put_nowait(
                    {
                        "records": poller_stat,
                        "topic": "sq-poller",
                        "schema": self.poller_schema,
                        "partition_cols": ["namespace", "hostname", "service"]
                    })

            # Post a command to fire up the next poll after the specified period
            self.logger.debug(
                f"Rescheduling service for {self.name} service")
            loop.call_later(self.period, self.call_node_postcmd,
                            self.node_postcall_list.get(token.nodename),
                            token.nodename)
