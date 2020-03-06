import os
import asyncio
import random
from datetime import datetime
import time
import copy
import logging
import json
import yaml
import sys
from tempfile import mkstemp

import pyarrow as pa

from suzieq.poller.services.svcparser import cons_recs_from_json_template

HOLD_TIME_IN_MSECS = 60000  # How long b4 declaring node dead


class Service(object):

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields or []
        self.queue = queue
        self.keys = keys
        self.schema = schema
        self.period = period
        self.stype = stype
        self.logger = logging.getLogger("suzieq")
        self.run_once = run_once

        self.update_nodes = False  # we have a new node list
        self.rebuild_nodelist = False  # used only when a node gets init
        self.nodes = {}
        self.new_nodes = {}

        # Add the hidden fields to ignore_fields
        self.ignore_fields.append("timestamp")

        if "datacenter" not in self.keys:
            self.keys.insert(0, "datacenter")

        if "hostname" not in self.keys:
            self.keys.insert(1, "hostname")

        if self.stype == "counters":
            self.partition_cols = ["datacenter", "hostname"]
        else:
            self.partition_cols = self.keys + ["timestamp"]

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

    def set_nodes(self, nodes):
        """New node list for this service"""
        if self.nodes:
            self.new_nodes = copy.deepcopy(nodes)
            self.update_nodes = True
        else:
            self.nodes = copy.deepcopy(nodes)

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

    async def gather_data(self):
        """Collect data invoking the appropriate get routine from nodes."""
        now = time.time()
        random.shuffle(self.nodelist)
        tasks = [self.nodes[key].exec_service(self.defn)
                 for key in self.nodelist]

        outputs = await asyncio.gather(*tasks)
        self.logger.info(
            f"gathered for {self.name} took {time.time() - now} seconds")
        return outputs

    def process_data(self, data):
        """Derive the data to be stored from the raw input"""
        result = []

        if int(data["status"]) == 200 or int(data["status"]) == 0:
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
        else:
            d = data.get("data", None)
            err = ""
            if d and isinstance(d, dict):
                err = d.get("error", "")
            self.logger.error(
                "{}: failed for node {} with {}/{}".format(
                    self.name, data["hostname"], data["status"],
                    err
                )
            )

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
            entry.update({"datacenter": raw_data["datacenter"]})
            entry.update({"timestamp": raw_data["timestamp"]})
            for fld in schema_rec:
                if fld not in entry:
                    if fld == "active":
                        entry.update({fld: True})
                    else:
                        entry.update({fld: schema_rec[fld]})

        return processed_data

    async def commit_data(self, result, datacenter, hostname):
        """Write the result data out"""
        records = []
        nodeobj = self.nodes.get(hostname, None)
        if not nodeobj:
            # This will be the case when a node switches from init state
            # to good after nodes have been built. Find the corresponding
            # node and fix the nodelist
            nres = [
                self.nodes[x] for x in self.nodes
                if self.nodes[x].hostname == hostname
            ]
            if nres:
                nodeobj = nres[0]
                prev_res = nodeobj.prev_result
                self.rebuild_nodelist = True
            else:
                logging.error(
                    "Ignoring results for {} which is not in "
                    "nodelist for service {}".format(hostname, self.name)
                )
                return
        else:
            prev_res = nodeobj.prev_result

        if result or prev_res:
            adds, dels = self.get_diff(prev_res, result)
            if adds or dels:
                nodeobj.prev_result = copy.deepcopy(result)
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
                self.queue.put_nowait(
                    {
                        "records": records,
                        "topic": self.name,
                        "schema": self.schema,
                        "partition_cols": self.partition_cols,
                    }
                )

    async def run(self):
        """Start the service"""
        self.logger.info(f"running service {self.name} ")
        self.nodelist = list(self.nodes.keys())

        while True:

            outputs = await self.gather_data()
            if self.run_once == "gather":
                print(self._dump_output(outputs))
                sys.exit(0)
            elif self.run_once == "process":
                poutputs = []
            for output in outputs:
                if not output:
                    # output from nodes not running service
                    continue
                result = self.process_data(output[0])
                # If a node from init state to good state, hostname will change
                # So fix that in the node list
                if self.run_once == "process":
                    poutputs += [{"datacenter": output[0]["datacenter"],
                                  "hostname": output[0]["hostname"],
                                  "output": result}]
                else:
                    await self.commit_data(
                        result, output[0]["datacenter"], output[0]["hostname"]
                    )

            if self.run_once == "process":
                print(self._dump_output(poutputs))
                sys.exit(0)

            if self.update_nodes:
                for node in self.new_nodes:
                    # Copy the last saved outputs to avoid committing dup data
                    if node in self.nodes:
                        self.new_nodes[node].prev_result = copy.deepcopy(
                            self.nodes[node].prev_result
                        )

                self.nodes = self.new_nodes
                self.nodelist = list(self.nodes.keys())
                self.new_nodes = {}
                self.update_nodes = False
                self.rebuild_nodelist = False

            elif self.rebuild_nodelist:
                adds = {}
                dels = []
                for host in self.nodes:
                    if self.nodes[host].hostname != host:
                        adds.update({self.nodes[host].hostname:
                                     self.nodes[host]})
                        dels.append(host)

                if dels:
                    for entry in dels:
                        self.nodes.pop(entry, None)

                if adds:
                    self.nodes.update(adds)

                self.nodelist = list(self.nodes.keys())
                self.rebuild_nodelist = False

            await asyncio.sleep(self.period + (random.randint(0, 1000) / 1000))
