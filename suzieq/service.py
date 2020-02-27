import os
import asyncio
import random
from datetime import datetime
import time
import re
import ast
import copy
import logging
import json
import yaml
import sys
from tempfile import mkstemp

import textfsm
import pyarrow as pa

HOLD_TIME_IN_MSECS = 60000  # How long b4 declaring node dead


def avro_to_arrow_schema(avro_sch):
    """Given an AVRO schema, return the equivalent Arrow schema"""
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
    }

    for fld in avro_sch.get("fields", None):
        if type(fld["type"]) is dict:
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


async def init_services(svc_dir, schema_dir, queue, run_once):
    """Process service definitions by reading each file in svc dir"""

    svcs_list = []
    svc_class_dict = {
        "system": SystemService,
        "interfaces": InterfaceService,
        "mlag": MlagService,
        "ospfIf": OspfIfService,
        "ospfNbr": OspfNbrService,
        "evpnVni": EvpnVniService,
        "routes": RoutesService,
        "arpnd": ArpndService,
        }

    if not os.path.isdir(svc_dir):
        logging.error("services directory not a directory: {}".format(svc_dir))
        return svcs_list

    if not os.path.isdir(schema_dir):
        logging.error("schema directory not a directory: {}".format(svc_dir))
        return svcs_list

    for root, _, filenames in os.walk(svc_dir):
        for filename in filenames:
            if filename.endswith("yml") or filename.endswith("yaml"):
                with open(root + "/" + filename, "r") as f:
                    svc_def = yaml.safe_load(f.read())
                if "service" not in svc_def or "apply" not in svc_def:
                    logging.error(
                        'Ignorning invalid service file definition. \
                    Need both "service" and "apply" keywords: {}'.format(
                            filename
                        )
                    )
                    continue

                period = svc_def.get("period", 15)
                for elem, val in svc_def["apply"].items():
                    if "copy" in val:
                        newval = svc_def["apply"].get(val["copy"], None)
                        if not newval:
                            logging.error(
                                "No device type {} to copy from for "
                                "{} for service {}".format(
                                    val["copy"], elem, svc_def["service"]
                                )
                            )
                            continue
                        val = newval

                    if "command" not in val or (
                        "normalize" not in val and "textfsm" not in val
                    ):
                        logging.error(
                            "Ignoring invalid service file "
                            'definition. Need both "command" and '
                            '"normalize/textfsm" keywords: {}, {}'.format(
                                filename, val)
                        )
                        continue

                    if "textfsm" in val:
                        # We may have already visited this element and parsed
                        # the textfsm file. Check for this
                        if val["textfsm"] and isinstance(
                            val["textfsm"], textfsm.TextFSM
                        ):
                            continue
                        tfsm_file = svc_dir + "/" + val["textfsm"]
                        if not os.path.isfile(tfsm_file):
                            logging.error(
                                "Textfsm file {} not found. Ignoring"
                                " service".format(tfsm_file)
                            )
                            continue
                        with open(tfsm_file, "r") as f:
                            tfsm_template = textfsm.TextFSM(f)
                            val["textfsm"] = tfsm_template
                    else:
                        tfsm_template = None

                # Find matching schema file
                fschema = "{}/{}.avsc".format(schema_dir, svc_def["service"])
                if not os.path.exists(fschema):
                    logging.error(
                        "No schema file found for service {}. "
                        "Ignoring service".format(svc_def["service"])
                    )
                    continue
                else:
                    with open(fschema, "r") as f:
                        schema = json.loads(f.read())
                    schema = avro_to_arrow_schema(schema)

                # Valid service definition, add it to list
                if svc_def["service"] in svc_class_dict:
                    service = svc_class_dict[svc_def["service"]](
                        svc_def["service"],
                        svc_def["apply"],
                        period,
                        svc_def.get("type", "state"),
                        svc_def.get("keys", []),
                        svc_def.get("ignore-fields", []),
                        schema,
                        queue,
                        run_once
                    )
                else:
                    service = Service(
                        svc_def["service"],
                        svc_def["apply"],
                        period,
                        svc_def.get("type", "state"),
                        svc_def.get("keys", []),
                        svc_def.get("ignore-fields", []),
                        schema,
                        queue,
                        run_once
                    )

                logging.info("Service {} added".format(service.name))
                svcs_list.append(service)

    return svcs_list


def stepdown_rest(entry) -> list:
    '''move the elements one level down into the existing JSON hierarchy.

    if `entry` has the structure {'vrfs': {'routes'...} on invocation,
    it'll be {'routes'...} on exit. It makes no sense to move down them
    hierarchy when you have only a list.
    '''
    if isinstance(entry["rest"], dict):
        keylist = list(entry["rest"].keys())
        data = entry["rest"]
        entry = []
        for key in keylist:
            entry += [{"rest": data[key]}]
    else:
        entry = [entry]

    return entry


def cons_recs_from_json_template(tmplt_str, in_data):
    ''' Return an array of records given the template and input data.

    This uses an XPATH-like template string to create a list of records
    matching the template. It also normalizes the key fields so that we
    can create records with keys that are agnostic of the source.

    I could not use a ready-made library like jsonpath because of the
    difficulty in handling normalization and how jsonpath returns the
    result. For example, if I have 3 route records, one with 2 nexthop IPs,
    one with a single nexthop IP and one without a nexthop IP, jsonpath
    returns the data as a single flat list of nexthop IPs without a hint of
    figuring out which route the nexthops correspond to. We also support
    some amount of additional processing on the extracted fields such as
    the basic 4 arithmetic operations and specifying a default or
    substitute.
    '''
    result = []
    # Find prefix string
    try:
        ppos = re.search(r'/\[\s+', tmplt_str).start()
    except AttributeError:
        ppos = tmplt_str.index('[')

    # templates have a structure with a leading hierarchy traversal
    # followed by the fields for each record within that hierarchy.
    # One example is: vrfs/*:vrf/routes/*:prefix/[... where '[' marks
    # the start of the template to extract the values from the route
    # records (prefix) across all the VRFs(vrf). We break up this
    # processing into two parts, one before we reach  the inner record
    # (before '[') and the other after.
    #
    # Before we enter the inner records, we flatten the hierarchy by
    # creating as many records as necessary with the container values
    # filled into each record as a separate key. So with the above
    # template, we transform the route records to carry the vrf and the
    # prefix as fields of each record. Thus, when we have 2 VRFs and 10
    # routes in the first VRF and 6 routes in the second VRF, before
    # we're done with the processing of the prefix hierarchy, the result
    # has 16 records (10+6 routes) with the VRF and prefix values contained
    # in each record.
    #
    # We flatten because that is how pandas (and pyarrow) can process the
    # data best and queries can be made simple. The only nested structure
    # we allow is a list in the innermost fields. Thus, the list of nexthop
    # IP addresses associated with a route or the list of IP addresses
    # associated with an interface are allowed, but not a tuple consisting
    # of the nexthopIP and oif as a single entry.
    data = in_data
    nokeys = True
    try:
        pos = tmplt_str.index("/")
    except ValueError:
        ppos = 0                # completely flat JSON struct
    while ppos > 0:
        xstr = tmplt_str[0:pos]

        if ":" not in xstr:
            if not result:
                if xstr != '*':
                    if not data or not data.get(xstr, None):
                        # Some outputs contain just the main key with a null
                        # body such as ospfNbr from EOS: {'vrfs': {}}.
                        return result
                    result = [{"rest": data[xstr]}]
                else:
                    result = [{"rest": []}]
                    for key in data.keys():
                        result[0]["rest"].append(data[key])
            else:
                if xstr != "*":
                    # Handle xstr being a specific array index or dict key
                    if xstr.startswith('['):
                        xstr = ast.literal_eval(xstr)
                        # result = list(map(stepdown_rest, result,
                        #                  repeat(xstr)))[0]
                        result[0]["rest"] = eval("{}{}".format(
                            result[0]["rest"], xstr))
                    else:
                        # result = list(map(stepdown_rest, result,
                        #                  repeat([xstr])))[0]
                        if xstr not in result[0]["rest"]:
                            return result
                        result[0]["rest"] = result[0]["rest"][xstr]
                else:
                    result = list(map(stepdown_rest, result))[0]

            tmplt_str = tmplt_str[pos+1:]
            try:
                pos = tmplt_str.index("/")
            except ValueError:
                # its ppossible the JSON data is entirely flat
                ppos = 0
                continue
            ppos -= pos
            continue

        lval, rval = xstr.split(":")
        nokeys = False
        ks = [lval]
        tmpres = []
        if result:
            for ele in result:
                if lval == "*":
                    ks = list(ele["rest"].keys())

                intres = [{rval: x,
                           "rest": ele["rest"][x]}
                          for x in ks]

                for oldkey in ele.keys():
                    if oldkey == "rest":
                        continue
                    for newele in intres:
                        newele.update({oldkey: ele[oldkey]})
                tmpres += intres
            result = tmpres
        else:
            if lval == "*":
                ks = list(data.keys())

            result = [{rval: x,
                       "rest": data[x]} for x in ks]

        tmplt_str = tmplt_str[pos+1:]
        pos = tmplt_str.index("/")
        ppos -= pos

    # Now for the rest of the fields
    # if we only have 'rest' as the key, break out into individual mbrs
    if nokeys:
        if not result:
            result = [{"rest": data}]
        elif len(result) == 1:
            tmpval = []
            for x in result[0]["rest"]:
                tmpval.append({"rest": x})
            result = tmpval

    # In some cases such as FRR's BGP, you need to eliminate elements which
    # have no useful 'rest' field, for example the elements with vrfId and
    # vrfName. If at this point, you have nn element in result with rest
    # that is not a list or a dict, remove it

    result = list(filter(lambda x: isinstance(x["rest"], list) or
                         isinstance(x["rest"], dict),
                         result))

    # The if handles cases of flat JSON data such as evpnVni
    if tmplt_str.startswith('/['):
        tmplt_str = tmplt_str[2:-1]
    else:
        tmplt_str = tmplt_str[1:][:-1]         # eliminate'[', ']'
    for selem in tmplt_str.split(","):
        # every element here MUST have the form lval:rval
        selem = selem.replace('"', '').strip()
        if not selem:
            # dealing with trailing "."
            continue

        lval, rval = selem.split(":")

        # Process default value processing of the form <key>?|<def_val> or
        # <key>?<expected_val>|<def_val>
        op = None
        if "?" in rval:
            rval, op = rval.split("?")
            exp_val, def_val = op.split("|")

            # Handle the case that the values are not strings
            if def_val.isdigit():
                def_val = int(def_val)
            elif def_val:
                # handle array indices
                try:
                    adef_val = ast.literal_eval(def_val)
                    def_val = adef_val
                except ValueError:
                    pass

        # Process for every element in result so far
        # Handles entries such as "vias/*/nexthopIps" and returns
        # a list of all nexthopIps.
        for x in result:
            if "/" in lval:
                subflds = lval.split("/")
                tmpval = x["rest"]
                value = None
                if "*" in subflds:
                    # Returning a list is the only supported option for now
                    value = []

                while subflds:
                    subfld = subflds.pop(0).strip()
                    if subfld == "*":
                        tmp = tmpval
                        for subele in tmp:
                            for ele in subflds:
                                if isinstance(tmp, list):
                                    subele = subele.get(ele, None)
                                else:
                                    subele = tmp[subele].get(ele, None)
                                if subele is None:
                                    break
                            if subele:
                                value.append(subele)
                        subflds = []
                    elif subfld.startswith('['):
                        # handle specific array index or dict key
                        # We don't handle a '*' in this position yet
                        assert(subfld != '[*]')
                        if tmpval:
                            tmpval = eval('tmpval{}'.format(subfld))
                    else:
                        tmpval = tmpval.get(subfld, None)
                    if not tmpval:
                        break

                if value is None:
                    value = tmpval
            else:
                value = x["rest"].get(lval.strip(), None)

            if op:
                if exp_val and value != exp_val:
                    value = def_val
                elif not exp_val and not value:
                    value = def_val

            # Handle any operation on string
            rval = rval.strip()
            rval1 = re.split(r"([+/*-])", rval)
            if len(rval1) > 1:
                iop = rval1[1]
                if value is not None:
                    if rval1[0] in x:
                        value = eval("{}{}{}".format(value, iop, x[rval1[0]]))
                    else:
                        value = eval("{}{}{}".format(value, iop, rval1[2]))
                try:
                    x.update({rval1[0]: value})
                except ValueError:
                    x.update({rval1[0]: value})
                continue

            x.update({rval: value})

    list(map(lambda x: x.pop("rest", None), result))

    return result


class Service(object):
    name = None
    defn = None
    period = 15  # 15s is the default period
    update_nodes = False  # we have a new node list
    rebuild_nodelist = False  # used only when a node gets init
    nodes = {}
    new_nodes = {}
    ignore_fields = []
    keys = []
    stype = "state"
    queue = None
    run_once = "forever"

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
        #textFSM objects can't be jsoned, so changing it
        for device in r['defn']:
            if 'textfsm' in r['defn'][device]:
                r['defn'][device]['textfsm'] = str(r['defn'][device]['textfsm'])
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
                    if type(entry[cent]) != ptype_map[schent_type]:
                        if entry[cent]:
                            entry[cent] = ptype_map[schent_type](entry[cent])
                        else:
                            entry[cent] = map_defaults[schent_type]
                    elif isinstance(entry[cent], list):
                        for i, ele in enumerate(entry[cent]):
                            if type(ele) != ptype_map[schent_type.value_type]:
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
        self.logger.info(f"gathered for {self.name} took {time.time() - now} seconds")
        return outputs

    def process_data(self, data):
        """Derive the data to be stored from the raw input"""
        result = []

        if data["status"] == 200 or data["status"] == 0:
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
                    if type(data["data"]) is str:
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
            if d:
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


class InterfaceService(Service):
    """Service class for interfaces. Cleanup of data is specific"""

    def clean_eos_data(self, processed_data):
        """Clean up EOS interfaces output"""
        for entry in processed_data:
            entry["speed"] = int(entry["speed"] / 1000000)
            ts = entry["statusChangeTimestamp"]
            if ts:
                entry["statusChangeTimestamp"] = int(float(ts) * 1000)
            else:
                entry["statusChangeTimestamp"] = 0
            if entry["type"] == "portChannel":
                entry["type"] = "bond"
            words = entry.get("master", "")
            if words:
                words = words.split()
                if words[-1].strip().startswith("Port-Channel"):
                    entry["type"] = "bond_slave"
                entry["master"] = words[-1].strip()
            entry["lacpBypass"] = (entry["lacpBypass"] == True)

            # Vlan is gathered as a list for VXLAN interfaces. Fix that
            if entry["type"] == "vxlan":
                entry["vlan"] = entry.get("vlan", [""])[0]

            tmpent = entry.get("ipAddressList", [[]])
            if not tmpent:
                continue

            munge_entry = tmpent[0]
            if munge_entry:
                new_list = []
                primary_ip = (
                    munge_entry["primaryIp"]["address"]
                    + "/"
                    + str(munge_entry["primaryIp"]["maskLen"])
                )
                new_list.append(primary_ip)
                for elem in munge_entry["secondaryIpsOrderedList"]:
                    ip = elem["adddress"] + "/" + elem["maskLen"]
                    new_list.append(ip)
                entry["ipAddressList"] = new_list

            # ip6AddressList is formatted as a dict, not a list by EOS
            munge_entry = entry.get("ip6AddressList", [{}])
            if munge_entry:
                new_list = []
                for elem in munge_entry.get("globalUnicastIp6s", []):
                    new_list.append(elem["subnet"])
                entry["ip6AddressList"] = new_list

    def clean_cumulus_data(self, processed_data):
        """We have to merge the appropriate outputs of two separate commands"""
        new_data_dict = {}
        for entry in processed_data:
            ifname = entry["ifname"]
            if entry.get('hardware', '') == 'ether':
                entry['hardware'] = 'ethernet'
            if ifname not in new_data_dict:

                if not entry['linkUpCnt']:
                    entry['linkUpCnt'] = 0
                if not entry['linkDownCnt']:
                    entry['linkDownCnt'] = 0

                entry["numChanges"] = int(entry["linkUpCnt"] +
                                          entry["linkDownCnt"])
                entry['state'] = entry['state'].lower()
                if entry["state"] == "up":
                    ts = entry["linkUpTimestamp"]
                else:
                    ts = entry["linkDownTimestamp"]
                if "never" in ts or not ts:
                    ts = 0
                else:
                    ts = int(
                        datetime.strptime(
                            ts.strip(), "%Y/%m/%d %H:%M:%S.%f"
                        ).timestamp()
                        * 1000
                    )
                entry["statusChangeTimestamp"] = ts

                del entry["linkUpCnt"]
                del entry["linkDownCnt"]
                del entry["linkUpTimestamp"]
                del entry["linkDownTimestamp"]
                del entry["vrf"]
                new_data_dict[ifname] = entry
            else:
                # Merge the two. The second entry is always from ip addr show
                # And it has the more accurate type, master list
                first_entry = new_data_dict[ifname]
                first_entry.update({"type": entry["type"]})
                first_entry.update({"master": entry["master"]})

        processed_data = []
        for _, v in new_data_dict.items():
            processed_data.append(v)

        return processed_data

    def clean_data(self, processed_data, raw_data):
        """Homogenize the IP addresses across different implementations
        Input:
            - list of processed output entries
            - raw unprocessed data
        Output:
            - processed output entries cleaned up
        """
        devtype = raw_data.get("devtype", None)
        if devtype == "eos":
            self.clean_eos_data(processed_data)
        elif devtype == "cumulus" or devtype == "platina":
            processed_data = self.clean_cumulus_data(processed_data)
        else:
            for entry in processed_data:
                entry['state'] = entry['state'].lower()

        return super().clean_data(processed_data, raw_data)


class SystemService(Service):
    """Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    """

    nodes_state = {}

    def __init__(self, name, defn, period, stype, keys, ignore_fields,
                 schema, queue, run_once):
        super().__init__(name, defn, period, stype, keys, ignore_fields,
                         schema, queue, run_once)
        self.ignore_fields.append("bootupTimestamp")

    def clean_data(self, processed_data, raw_data):
        """Cleanup the bootup timestamp for Linux nodes"""

        for entry in processed_data:
            # We're assuming that if the entry doesn't provide the
            # bootupTimestamp field but provides the sysUptime field,
            # we fix the data so that it is always bootupTimestamp
            # TODO: Fix the clock drift
            if not entry.get("bootupTimestamp", None) and entry.get(
                    "sysUptime", None):
                entry["bootupTimestamp"] = int(
                    raw_data["timestamp"]/1000 - float(entry["sysUptime"])
                )
                del entry["sysUptime"]
            # This is the case for Linux servers, so also extract the vendor
            # and version from the os string
            if not entry.get("vendor", ''):
                if 'os' in entry:
                    osstr = entry.get("os", "").split()
                    if len(osstr) > 1:
                        # Assumed format is: Ubuntu 18.04.2 LTS,
                        # CentOS Linux 7 (Core)
                        entry["vendor"] = osstr[0]
                        if not entry.get("version", ""):
                            entry["version"] = ' '.join(osstr[1:])
                    del entry["os"]

            entry['status'] = "alive"
            entry["address"] = raw_data["address"]
        return super().clean_data(processed_data, raw_data)

    async def commit_data(self, result, datacenter, hostname):
        """system svc needs to write out a record that indicates dead node"""
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
            else:
                logging.error(
                    "Ignoring results for {} which is not in "
                    "nodelist for service {}".format(hostname, self.name)
                )
                return

        if not result:
            if nodeobj.get_status() == "init":
                # If in init still, we need to mark the node as unreachable
                rec = self.get_empty_record()
                rec["datacenter"] = datacenter
                rec["hostname"] = hostname
                rec["timestamp"] = int(datetime.utcnow().timestamp() * 1000)
                rec["status"] = "dead"
                rec["active"] = True

                result.append(rec)
            elif nodeobj.get_status() == "good":
                # To avoid unnecessary flaps, we wait for HOLD_TIME to expire
                # before we mark the node as dead
                if hostname in self.nodes_state:
                    now = int(datetime.utcnow().timestamp() * 1000)
                    if now - self.nodes_state[hostname] > HOLD_TIME_IN_MSECS:
                        prev_res = nodeobj.prev_result
                        if prev_res:
                            result = copy.deepcopy(prev_res)
                        else:
                            record = self.get_empty_record()
                            record["datacenter"] = datacenter
                            record["hostname"] = hostname
                            result = [record]

                        result[0]["status"] = "dead"
                        result[0]["timestamp"] = self.nodes_state[hostname]
                        del self.nodes_state[hostname]
                        nodeobj.set_unreach_status()
                    else:
                        return
                else:
                    self.nodes_state[hostname] = int(
                        datetime.utcnow().timestamp() * 1000
                    )
                    return
            else:
                # Ensure we don't delete the dead entry
                prev_res = nodeobj.prev_result
                if prev_res:
                    result = copy.deepcopy(prev_res)
                    result[0]["timestamp"] = int(
                        datetime.utcnow().timestamp() * 1000
                    )
        else:
            # Clean up old state if any since we now have a valid output
            if self.nodes_state.get(hostname, None):
                del self.nodes_state[hostname]
            nodeobj.set_good_status()

        await super().commit_data(result, datacenter, hostname)

    def get_diff(self, old, new):

        adds = []
        dels = []
        koldvals = {}
        knewvals = {}

        for i, elem in enumerate(old):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            koldvals.update({tuple(str(vals)): i})

        for i, elem in enumerate(new):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            knewvals.update({tuple(str(vals)): i})

        addlist = [v for k, v in knewvals.items() if k not in koldvals.keys()]
        dellist = [v for k, v in koldvals.items() if k not in knewvals.keys()]

        adds = [new[v] for v in addlist]
        dels = [old[v] for v in dellist]

        if not (adds or dels):
            # Verify the bootupTimestamp hasn't changed. Compare only int part
            # Assuming no device boots up in millisecs
            if abs(int(new[0]["bootupTimestamp"]) -
                   int(old[0]["bootupTimestamp"])) > 2:
                adds.append(new[0])

        return adds, dels


class MlagService(Service):
    """MLAG service. Different class because output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        if raw_data.get("devtype", None) == "cumulus":
            mlagDualPortsCnt = 0
            mlagSinglePortsCnt = 0
            mlagErrorPortsCnt = 0
            mlagDualPorts = []
            mlagSinglePorts = []
            mlagErrorPorts = []

            for entry in processed_data:
                if entry['state']:
                    entry['state'] = 'active'
                else:
                    entry['state'] = 'inactive'
                mlagIfs = entry["mlagInterfacesList"]
                for mlagif in mlagIfs:
                    if mlagIfs[mlagif]["status"] == "dual":
                        mlagDualPortsCnt += 1
                        mlagDualPorts.append(mlagif)
                    elif mlagIfs[mlagif]["status"] == "single":
                        mlagSinglePortsCnt += 1
                        mlagSinglePorts.append(mlagif)
                    elif (
                        mlagIfs[mlagif]["status"] == "errDisabled"
                        or mlagif["status"] == "protoDown"
                    ):
                        mlagErrorPortsCnt += 1
                        mlagErrorPorts.append(mlagif)
                entry["mlagDualPorts"] = mlagDualPorts
                entry["mlagSinglePorts"] = mlagSinglePorts
                entry["mlagErrorPorts"] = mlagErrorPorts
                entry["mlagSinglePortsCnt"] = mlagSinglePortsCnt
                entry["mlagDualPortsCnt"] = mlagDualPortsCnt
                entry["mlagErrorPortsCnt"] = mlagErrorPortsCnt
                del entry["mlagInterfacesList"]

        return super().clean_data(processed_data, raw_data)


class OspfIfService(Service):
    """OSPF Interface service. Output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        dev_type = raw_data.get("devtype", None)
        if dev_type == "cumulus" or dev_type == "linux":
            for entry in processed_data:
                entry["vrf"] = "default"
                entry["networkType"] = entry["networkType"].lower()
                entry["passive"] = entry["passive"] == "Passive"
                entry["isUnnumbered"] = entry["isUnnumbered"] == "UNNUMBERED"
                entry["areaStub"] = entry["areaStub"] == "[Stub]"
        elif raw_data.get("devtype", None) == "eos":
            for entry in processed_data:
                entry["networkType"] = entry["networkType"].lower()
                entry["passive"] = entry["passive"] == "Passive"
                entry["isUnnumbered"] = False
                entry["areaStub"] = False  # Fix this
        return super().clean_data(processed_data, raw_data)


class OspfNbrService(Service):
    """OSPF Neighbor service. Output needs to be munged"""

    def frr_convert_reltime_to_epoch(self, reltime):
        """Convert string of type 1d12h3m23s into absolute epoch"""
        secs = 0
        s = reltime
        for t, mul in {
            "w": 3600 * 24 * 7,
            "d": 3600 * 24,
            "h": 3600,
            "m": 60,
            "s": 1,
        }.items():
            v = s.split(t)
            if len(v) == 2:
                secs += int(v[0]) * mul
            s = v[-1]

        return int((datetime.utcnow().timestamp() - secs) * 1000)

    def clean_data(self, processed_data, raw_data):

        dev_type = raw_data.get("devtype", None)
        if dev_type == "cumulus" or dev_type == "linux":
            for entry in processed_data:
                entry["vrf"] = "default"
                entry["state"] = entry["state"].lower()
                entry["lastChangeTime"] = self.frr_convert_reltime_to_epoch(
                    entry["lastChangeTime"]
                )
                entry["areaStub"] = entry["areaStub"] == "[Stub]"
        elif dev_type == "eos":
            for entry in processed_data:
                entry["state"] = entry["state"].lower()
                entry["lastChangeTime"] = int(entry["lastChangeTime"] * 1000)

        return super().clean_data(processed_data, raw_data)


class EvpnVniService(Service):
    """evpnVni service. Different class because output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        if raw_data.get("devtype", None) == "cumulus":
            for entry in processed_data:
                if entry["numRemoteVteps"] == "n/a":
                    entry["numRemoteVteps"] = 0
                if entry["remoteVteps"] == '':
                    entry["remoteVteps"] == []
        return super().clean_data(processed_data, raw_data)


class RoutesService(Service):
    """routes service. Different class because vrf default needs to be added"""

    def clean_data(self, processed_data, raw_data):

        devtype = raw_data.get("devtype", None)
        if any([devtype == x for x in ["cumulus", "linux", "platina"]]):
            for entry in processed_data:
                entry["vrf"] = entry["vrf"] or "default"
                entry["metric"] = entry["metric"] or 20
                for ele in ["nexthopIps", "oifs"]:
                    entry[ele] = entry[ele] or [""]
                entry["weights"] = entry["weights"] or [1]
                if entry['prefix'] == 'default':
                    entry['prefix'] = '0.0.0.0/0'

        return super().clean_data(processed_data, raw_data)


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def clean_data(self, processed_data, raw_data):

        devtype = raw_data.get("devtype", None)
        if any([devtype == x for x in ["cumulus", "linux", "platina"]]):
            for entry in processed_data:
                entry["offload"] = entry["offload"] == "offload"
                entry["state"] = entry["state"].lower()

        return super().clean_data(processed_data, raw_data)
