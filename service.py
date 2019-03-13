

import os
import asyncio
import random
import time
from datetime import datetime
import re
import ast
import copy
import logging
import json

import yaml

import textfsm
import pyarrow as pa

HOLD_TIME_IN_MSECS = 60000    # How long b4 declaring node dead

def avro_to_arrow_schema(avro_sch):
    '''Given an AVRO schema, return the equivalent Arrow schema'''
    arsc_fields = []

    map_type = {'string': pa.string(),
                'long': pa.int64(),
                'int': pa.int32(),
                'double': pa.float64(),
                'float': pa.float32(),
                'timestamp': pa.int64(),
                'timedelta64[s]': pa.float64(),
                'boolean': pa.bool_(),
                'array.string': pa.list_(pa.string()),
                'array.long': pa.list_(pa.int64())
                }

    for fld in avro_sch.get('fields', None):
        if type(fld['type']) is dict:
            if fld['type']['type'] == 'array':
                avtype: str = 'array.{}'.format(fld['type']['items']['type'])
            else:
                # We don't support map yet
                raise AttributeError
        else:
            avtype: str = fld['type']

        arsc_fields.append(pa.field(fld['name'], map_type[avtype]))

    return pa.schema(arsc_fields)


async def init_services(svc_dir, schema_dir, queue):
    '''Process service definitions by reading each file in svc dir'''

    svcs_list = []

    if not os.path.isdir(svc_dir):
        logging.error('services directory not a directory: {}'.format(svc_dir))
        return svcs_list

    if not os.path.isdir(schema_dir):
        logging.error('schema directory not a directory: {}'.format(svc_dir))
        return svcs_list

    for root, _, filenames in os.walk(svc_dir):
        for filename in filenames:
            if filename.endswith('yml') or filename.endswith('yaml'):
                with open(root + '/' + filename, 'r') as f:
                    svc_def = yaml.load(f.read())
                if 'service' not in svc_def or 'apply' not in svc_def:
                    logging.error('Ignorning invalid service file definition. \
                    Need both "service" and "apply" keywords: {}'
                                  .format(filename))
                    continue

                period = svc_def.get('period', 15)
                for elem, val in svc_def['apply'].items():
                    if 'copy' in val:
                        newval = svc_def['apply'].get(val['copy'], None)
                        if not newval:
                            logging.error('No device type {} to copy from for '
                                          '{} for service {}'
                                          .format(val['copy'], elem,
                                                  svc_def['service']))
                            continue
                        val = newval

                    if ('command' not in val or
                            ('normalize' not in val and 'textfsm' not in val)):
                        logging.error('Ignoring invalid service file '
                                      'definition. Need both "command" and '
                                      '"normalize/textfsm" keywords: {}, {}'
                                      .format(filename, val))
                        continue

                    if 'textfsm' in val:
                        # We may have already visited this element and parsed
                        # the textfsm file. Check for this
                        if val['textfsm'] and isinstance(val['textfsm'],
                                                         textfsm.TextFSM):
                            continue
                        tfsm_file = svc_dir + '/' + val['textfsm']
                        if not os.path.isfile(tfsm_file):
                            logging.error('Textfsm file {} not found. Ignoring'
                                          ' service'.format(tfsm_file))
                            continue
                        with open(tfsm_file, 'r') as f:
                            tfsm_template = textfsm.TextFSM(f)
                            val['textfsm'] = tfsm_template
                    else:
                        tfsm_template = None

                # Find matching schema file
                fschema = '{}/{}.avsc'.format(schema_dir, svc_def['service'])
                if not os.path.exists(fschema):
                    logging.error('No schema file found for service {}. '
                                  'Ignoring service'.format(
                                      svc_def['service']))
                    continue
                else:
                    with open(fschema, 'r') as f:
                        schema = json.loads(f.read())
                    schema = avro_to_arrow_schema(schema)

                # Valid service definition, add it to list
                if svc_def['service'] == 'interfaces':
                    service = InterfaceService(svc_def['service'],
                                               svc_def['apply'],
                                               period,
                                               svc_def.get('type', 'state'),
                                               svc_def.get('keys', []),
                                               svc_def.get('ignore-fields',
                                                           []),
                                               schema, queue)
                elif svc_def['service'] == 'system':
                    service = SystemService(svc_def['service'],
                                            svc_def['apply'],
                                            period,
                                            svc_def.get('type', 'state'),
                                            svc_def.get('keys', []),
                                            svc_def.get('ignore-fields', []),
                                            schema, queue)
                elif svc_def['service'] == 'mlag':
                    service = MlagService(svc_def['service'],
                                          svc_def['apply'],
                                          period,
                                          svc_def.get('type', 'state'),
                                          svc_def.get('keys', []),
                                          svc_def.get('ignore-fields', []),
                                          schema, queue)
                elif svc_def['service'] == 'ospfIf':
                    service = OspfIfService(svc_def['service'],
                                            svc_def['apply'],
                                            period,
                                            svc_def.get('type', 'state'),
                                            svc_def.get('keys', []),
                                            svc_def.get('ignore_fields', []),
                                            schema, queue)
                elif svc_def['service'] == 'ospfNbr':
                    service = OspfNbrService(svc_def['service'],
                                             svc_def['apply'],
                                             period,
                                             svc_def.get('type', 'state'),
                                             svc_def.get('keys', []),
                                             svc_def.get('ignore_fields', []),
                                             schema, queue)
                else:
                    service = Service(svc_def['service'], svc_def['apply'],
                                      period, svc_def.get('type', 'state'),
                                      svc_def.get('keys', []),
                                      svc_def.get('ignore-fields', []),
                                      schema, queue)

                logging.info('Service {} added'.format(service.name))
                svcs_list.append(service)

    return svcs_list


class Service(object):
    name = None
    defn = None
    period = 15                 # 15s is the default period
    update_nodes = False        # we have a new node list
    rebuild_nodelist = False    # used only when a node gets init
    nodes = {}
    new_nodes = {}
    ignore_fields = []
    keys = []
    stype = 'state'
    queue = None

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields
        self.queue = queue
        self.keys = keys
        self.schema = schema
        self.period = period
        self.stype = stype

        self.logger = logging.getLogger('suzieq')

        # Add the hidden fields to ignore_fields
        self.ignore_fields.append('timestamp')

        if 'datacenter' not in self.keys:
            self.keys.insert(0, 'datacenter')

        if 'hostname' not in self.keys:
            self.keys.insert(1, 'hostname')

    def set_nodes(self, nodes):
        '''New node list for this service'''
        if self.nodes:
            self.new_nodes = copy.deepcopy(nodes)
            self.update_nodes = True
        else:
            self.nodes = copy.deepcopy(nodes)

    def get_empty_record(self):
        map_defaults = {
            pa.string(): '',
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

    def get_diff(self, old, new):
        '''Compare list of dictionaries ignoring certain fields
        Return list of adds and deletes
        '''
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

        if adds and self.stype == 'counters':
            # If there's a change in any field of the counters, update them all
            # simplifies querying
            adds = new

        return adds, dels

    def exdict(self, path, data, start, collect=False):
        '''Extract all fields in specified path from data'''

        def set_kv(okeys, indata, oresult):
            '''Set the value in the outgoing dict'''
            if okeys:
                okeys = [okeys[0].strip(), okeys[1].strip()]
                cval = indata.get(okeys[0], '') if indata else ''

            if '?' in okeys[1]:
                fkey, fvals = okeys[1].split('?')
                fvals = fvals.split('|')
                if '=' in fvals[0]:
                    tval, rval = fvals[0].split('=')
                else:
                    tval = fvals[0]
                    rval = fvals[0]
                tval = tval.strip()
                rval = rval.strip()
                # String a: b?|False => if not a's value, use False, else use a
                # String a: b?True=active|inactive => if a's value is true, use_key
                # the string 'active' instead else use inactive
                # String a: b?True=active| => if a's value is True, switch to
                # active else leave it as it is
                if not cval or (tval and str(cval) != tval):
                    if fvals[1]:
                        try:
                            oresult[fkey.strip()] = ast.literal_eval(fvals[1])
                        except (ValueError, SyntaxError):
                            oresult[fkey.strip()] = fvals[1]
                    else:
                        oresult[fkey.strip()] = cval
                elif cval and not tval:
                    oresult[fkey.strip()] = cval
                else:
                    oresult[fkey.strip()] = rval
            else:
                opmatch = re.match(r'^(add|sub|mul|div)\((\w+),(\w+)\)$', okeys[1])
                if opmatch:
                    op, lval, rval = opmatch.groups()
                    if rval not in oresult:
                        if not rval.isdigit():
                            # This is an unsuppported operation, need int field
                            oresult[lval] = 0
                            return
                        else:
                            rval = int(rval)
                    else:
                        rval = int(oresult[rval])
                    if not cval:
                        cval = 0
                    if op == 'add':
                        oresult[lval] = cval + rval
                    elif op == 'sub':
                        oresult[lval] = cval - rval
                    elif op == 'mul':
                        oresult[lval] = cval * rval
                    elif op == 'div':
                        if rval:
                            oresult[lval] = cval / rval
                        else:
                            oresult[lval] = 0
                else:
                    rval = cval
                    try:
                        oresult[okeys[1].strip()] = ast.literal_eval(rval)
                    except (ValueError, SyntaxError):
                        oresult[okeys[1].strip()] = rval
            return

        result = []
        iresult = {}

        plist = re.split('''/(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', path)
        i = 0
        for i, elem in enumerate(plist[start:]):

            if not data:
                if '[' not in plist[-1] and ':' in plist[-1]:
                    set_kv(plist[-1].split(':'), data, iresult)
                    result.append(iresult)
                return result, i+start

            j = 0
            num = re.match(r'\[([0-9]*)\]', elem)
            if num:
                data = data[int(num.group(1))]

            elif elem.startswith('*'):
                use_key = False
                is_list = True
                if type(data) is dict:
                    is_list = False
                    okeys = elem.split(':')
                    if len(okeys) > 1:
                        use_key = True

                if plist[-1] == elem and collect:
                    # We're a leaf now. So, suck up the list or dict if
                    # we're to collect
                    if is_list:
                        cstr = data
                    else:
                        cstr = [k for k in data]
                    set_kv(okeys, {'*': cstr}, iresult)
                    result.append(iresult)
                    return result, i + start

                for item in data:
                    if not is_list:
                        datum = data[item]
                    else:
                        datum = item
                    if type(datum) is dict or type(datum) is list:
                        if use_key:
                            if collect:
                                # We're at the leaf and just gathering the fields
                                # as a comma separated string
                                # example: memberInterfaces/* : lacpMembers
                                cstr = ''
                                for key in data:
                                    cstr = cstr + ', ' + key if cstr else key
                                iresult[okeys[1].strip()] = cstr
                                result.append(iresult)
                                return result, i + start
                            iresult[okeys[1].strip()] = item
                        tmpres, j = self.exdict(path, datum, start+i+1)
                        if tmpres:
                            for subresult in tmpres:
                                iresult.update(subresult)
                                result.append(iresult)
                                iresult = {}
                                if use_key:
                                    iresult[okeys[1].strip()] = item
                    else:
                        continue
                if j >= i:
                    break
            elif type(elem) is str:
                # split the normalized key and data key
                okeys = elem.split(':')
                if okeys[0] in data:
                    if start+i+1 == len(plist):
                        set_kv(okeys, data, iresult)
                        result.append(iresult)
                    else:
                        data = data[okeys[0]]
                else:
                    try:
                        fields = ast.literal_eval(elem)
                    except (ValueError, SyntaxError):
                        # Catch if the elem is a string key not present in the data
                        # Case of missing key, abort if necessary
                        # if not path.endswith(']') and ':' in plist[-1]:
                        if ':' in plist[-1]:
                            okeys = plist[-1].split(':')
                            set_kv(okeys, data, iresult)
                            result.append(iresult)
                            return result, i+start

                    if type(fields) is list:
                        for fld in fields:
                            if '/' in fld:
                                sresult, _ = self.exdict(fld, data, 0,
                                                         collect=True)
                                for res in sresult:
                                    iresult.update(res)
                            else:
                                okeys = fld.split(':')
                                set_kv(okeys, data, iresult)
                        result.append(iresult)
                        iresult = {}

        return result, i+start

    def textfsm_data(self, raw_input, fsm_template, schema, data):
        '''Convert unstructured output to structured output'''

        records = []
        fsm_template.Reset()
        res = fsm_template.ParseText(raw_input)

        for entry in res:
            metent = dict(zip(fsm_template.header, entry))
            records.append(metent)

        result = self.clean_data(records, data)

        fields = [fld.name for fld in schema]

        ptype_map = {pa.string(): str,
                     pa.int32(): int,
                     pa.int64(): int,
                     pa.float32(): float,
                     pa.float64(): float,
                     pa.date64(): float,
                     pa.list_(pa.string()): list,
                     pa.bool_(): bool
                     }

        map_defaults = {
            pa.string(): '',
            pa.int32(): 0,
            pa.int64(): 0,
            pa.float32(): 0.0,
            pa.float64(): 0.0,
            pa.date64(): 0.0,
            pa.bool_(): False,
            pa.list_(pa.string()): [],
            pa.list_(pa.int64()): [],
            }

        # Ensure the type is set correctly.
        for entry in result:
            for cent in entry:
                if cent in fields:
                    schent_type = schema.field_by_name(cent).type
                    if type(entry[cent]) != ptype_map[schent_type]:
                        if entry[cent]:
                            entry[cent] = ptype_map[schent_type](entry[cent])
                        else:
                            entry[cent] = map_defaults[schent_type]

        return result

    async def gather_data(self):
        '''Collect data invoking the appropriate get routine from nodes.'''

        random.shuffle(self.nodelist)
        tasks = [self.nodes[key].exec_service(self.defn)
                 for key in self.nodelist]

        outputs = await asyncio.gather(*tasks)

        return outputs

    def process_data(self, data):
        '''Derive the data to be stored from the raw input'''
        result = []

        if data['status'] == 200 or data['status'] == 0:
            if not data['data']:
                return result

            nfn = self.defn.get(data.get('hostname'), None)
            if not nfn:
                nfn = self.defn.get(data.get('devtype'), None)
            if nfn:
                copynfn = nfn.get('copy', None)
                if copynfn:
                    nfn = self.defn.get(copynfn, {})
                if nfn.get('normalize', None):
                    if type(data['data']) is str:
                        try:
                            in_info = json.loads(data['data'])
                        except json.JSONDecodeError:
                            self.logger.error('Received non-JSON output where '
                                              'JSON was expected for {} on '
                                              'node {}, {}'.format(
                                                  data['cmd'],
                                                  data['hostname'],
                                                  data['data']))
                            return result
                    else:
                        in_info = data['data']

                    result, _ = self.exdict(nfn.get('normalize', ''), in_info,
                                            0)

                    result = self.clean_data(result, data)
                else:
                    tfsm_template = nfn.get('textfsm', None)
                    if not tfsm_template:
                        return result

                    if 'output' in data['data']:
                        in_info = data['data']['output']
                    elif 'messages' in data['data']:
                        # This is Arista's bash output format
                        in_info = data['data']['messages'][0]
                    else:
                        in_info = data['data']
                    # Clean data is invoked inside this due to the way we
                    # munge the data and force the types to adhere to the
                    # specified type
                    result = self.textfsm_data(in_info, tfsm_template,
                                               self.schema, data)
            else:
                self.logger.error(
                    '{}: No normalization/textfsm function for device {}'
                    .format(self.name, data['hostname']))
        else:
            self.logger.error('{}: failed for node {} with {}/{}'.format(
                self.name, data['hostname'], data['status'],
                data.get('error', '')))

        return result

    def clean_data(self, processed_data, raw_data):

        # Build default data structure
        schema_rec = {}
        def_vals = {pa.string(): '-', pa.int32(): 0, pa.int64(): 0,
                    pa.float64(): 0, pa.float32(): 0.0, pa.bool_(): False,
                    pa.date64(): 0.0, pa.list_(pa.string()): ['-']}
        for field in self.schema:
            default = def_vals[field.type]
            schema_rec.update({field.name: default})

        for entry in processed_data:
            entry.update({'hostname': raw_data['hostname']})
            entry.update({'datacenter': raw_data['datacenter']})
            entry.update({'timestamp': raw_data['timestamp']})
            for fld in schema_rec:
                if fld not in entry:
                    if fld == 'active':
                        entry.update({fld: True})
                    else:
                        entry.update({fld: schema_rec[fld]})

        return processed_data

    async def commit_data(self, result, datacenter, hostname):
        '''Write the result data out'''
        records = []
        nodeobj = self.nodes.get(hostname, None)
        if not nodeobj:
            # This will be the case when a node switches from init state
            # to good after nodes have been built. Find the corresponding
            # node and fix the nodelist
            nres = [self.nodes[x] for x in self.nodes
                    if self.nodes[x].hostname == hostname]
            if nres:
                nodeobj = nres[0]
                prev_res = nodeobj.prev_result
                self.rebuild_nodelist = True
            else:
                logging.error('Ignoring results for {} which is not in '
                              'nodelist for service {}'.format(hostname,
                                                               self.name))
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
                    if entry.get('active', True):
                        # If there's already an entry marked as deleted
                        # No point in adding one more
                        entry.update({'active': False})
                        entry.update({'timestamp': int(time.time()*1000)})
                        records.append(entry)

            if records:
                if self.stype == 'counters':
                    partition_cols = ['datacenter', 'hostname']
                else:
                    partition_cols = self.keys + ['timestamp']

                self.queue.put_nowait({'records': records,
                                       'topic': self.name,
                                       'schema': self.schema,
                                       'partition_cols': partition_cols})

    async def run(self):
        '''Start the service'''

        self.nodelist = list(self.nodes.keys())

        while True:

            outputs = await self.gather_data()
            for output in outputs:
                if not output:
                    # output from nodes not running service
                    continue
                result = self.process_data(output[0])
                # If a node from init state to good state, hostname will change
                # So fix that in the node list

                await self.commit_data(result, output[0]['datacenter'],
                                       output[0]['hostname'])

            if self.update_nodes:
                for node in self.new_nodes:
                    # Copy the last saved outputs to avoid committing dup data
                    if node in self.nodes:
                        self.new_nodes[node].prev_result = (
                            copy.deepcopy(self.nodes[node].prev_result))

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

            await asyncio.sleep(self.period + (random.randint(0, 1000)/1000))


class InterfaceService(Service):
    '''Service class for interfaces. Cleanup of data is specific'''

    def clean_eos_data(self, processed_data):
        '''Clean up EOS interfaces output'''
        for entry in processed_data:
            entry['speed'] = int(entry['speed']/1000000)
            ts = entry['statusChangeTimestamp']
            if ts:
                entry['statusChangeTimestamp'] = int(float(ts)*1000)
            else:
                entry['statusChangeTimestamp'] = 0
            if entry['type'] == 'portChannel':
                entry['type'] = 'bond'
            words = entry['master'].split()
            if words:
                if words[-1].strip().startswith('Port-Channel'):
                    entry['type'] = 'bond_slave'
                entry['master'] = words[-1].strip()

            # Vlan is gathered as a list for VXLAN interfaces. Fix that
            if entry['type'] == 'vxlan':
                entry['vlan'] = entry.get('vlan', [''])[0]

            tmpent = entry.get('ipAddressList', [[]])
            if not tmpent:
                continue

            munge_entry = tmpent[0]
            if munge_entry:
                new_list = []
                primary_ip = (
                    munge_entry['primaryIp']['address'] + '/' +
                    str(munge_entry['primaryIp']['maskLen'])
                )
                new_list.append(primary_ip)
                for elem in munge_entry['secondaryIpsOrderedList']:
                    ip = elem['adddress'] + '/' + elem['maskLen']
                    new_list.append(ip)
                entry['ipAddressList'] = new_list

            # ip6AddressList is formatted as a dict, not a list by EOS
            munge_entry = entry.get('ip6AddressList', [{}])
            if munge_entry:
                new_list = []
                for elem in munge_entry.get('globalUnicastIp6s', []):
                    new_list.append(elem['subnet'])
                entry['ip6AddressList'] = new_list

    def clean_cumulus_data(self, processed_data):
        '''We have to merge the appropriate outputs of two separate commands'''
        new_data_dict = {}
        for entry in processed_data:
            ifname = entry['ifname']
            if ifname not in new_data_dict:
                entry['transitionCnt'] = int(entry['linkUpCnt'] +
                                             entry['linkDownCnt'])
                if entry['state'] == 'up':
                    ts = entry['linkUpTimestamp']
                else:
                    ts = entry['linkDownTimestamp']
                if 'never' in ts:
                    ts = 0
                else:
                    ts = int(datetime.strptime(
                        ts.strip(), '%Y/%m/%d %H:%M:%S.%f').timestamp() * 1000)
                entry['statusChangeTimestamp'] = ts

                del entry['linkUpCnt']
                del entry['linkDownCnt']
                del entry['linkUpTimestamp']
                del entry['linkDownTimestamp']
                del entry['vrf']
                new_data_dict[ifname] = entry
            else:
                # Merge the two. The second entry is always from ip addr show
                # And it has the more accurate type, master list
                first_entry = new_data_dict[ifname]
                first_entry.update({'type': entry['type']})
                first_entry.update({'master': entry['master']})

        processed_data = []
        for _, v in new_data_dict.items():
            processed_data.append(v)

        return processed_data

    def clean_data(self, processed_data, raw_data):
        '''Homogenize the IP addresses across different implementations
        Input:
            - list of processed output entries
            - raw unprocessed data
        Output:
            - processed output entries cleaned up
        '''
        devtype = raw_data.get('devtype', None)
        if devtype == 'eos':
            self.clean_eos_data(processed_data)
        elif devtype == 'cumulus' or devtype == 'platina':
            processed_data = self.clean_cumulus_data(processed_data)

        return super().clean_data(processed_data, raw_data)

class SystemService(Service):
    '''Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    '''
    nodes_state = {}

    def __init__(self, name, defn, period, stype, keys, ignore_fields,
                 schema, queue):
        super().__init__(name, defn, period, stype, keys,
                         ignore_fields, schema, queue)
        self.ignore_fields.append('bootupTimestamp')

    def clean_data(self, processed_data, raw_data):
        '''Cleanup the bootup timestamp for Linux nodes'''

        for entry in processed_data:
            # We're assuming that if the entry doesn't provide the
            # bootupTimestamp field but provides the sysUptime field,
            # we fix the data so that it is always bootupTimestamp
            # TODO: Fix the clock drift
            if (not entry.get('bootupTimestamp', None) and
                    entry.get('sysUptime', None)):
                entry['bootupTimestamp'] = int(
                    raw_data['timestamp']/1000 - float(entry.get('sysUptime')))
                del entry['sysUptime']

        return super().clean_data(processed_data, raw_data)

    async def commit_data(self, result, datacenter, hostname):
        '''system svc needs to write out a record that indicates dead node'''
        nodeobj = self.nodes.get(hostname, None)
        if not nodeobj:
            # This will be the case when a node switches from init state
            # to good after nodes have been built. Find the corresponding
            # node and fix the nodelist
            nres = [self.nodes[x] for x in self.nodes
                    if self.nodes[x].hostname == hostname]
            if nres:
                nodeobj = nres[0]
            else:
                logging.error('Ignoring results for {} which is not in '
                              'nodelist for service {}'.format(hostname,
                                                               self.name))
                return

        if not result:
            if nodeobj.get_status() == 'init':
                # If in init still, we need to mark the node as unreachable
                rec = self.get_empty_record()
                rec['datacenter'] = datacenter
                rec['hostname'] = hostname
                rec['timestamp'] = int(time.time() * 1000)

                result.append(rec)
            elif nodeobj.get_status == 'good':
                # To avoid unnecessary flaps, we wait for HOLD_TIME to expire
                # before we mark the node as dead
                if hostname in self.nodes_state:
                    now = int(time.time() * 1000)
                    if now - self.nodes_state[hostname] > HOLD_TIME_IN_MSECS:
                        prev_res = nodeobj.prev_result
                        if prev_res:
                            result = copy.deepcopy(prev_res)
                        else:
                            record = self.get_empty_record()
                            record['datacenter'] = datacenter
                            record['hostname'] = hostname
                            result = [record]

                        result[0]['active'] = False
                        result[0]['timestamp'] = self.nodes_state[hostname]
                        del self.nodes_state[hostname]
                        nodeobj.set_unreach_status()
                    else:
                        return
                else:
                    self.nodes_state[hostname] = int(time.time() * 1000)
                    return
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
            if abs(int(new[0]['bootupTimestamp']) - int(old[0]['bootupTimestamp'])) > 2:
                adds.append(new[0])

        return adds, dels


class MlagService(Service):
    '''MLAG service. Different class because output needs to be munged'''

    def clean_data(self, processed_data, raw_data):

        if raw_data.get('devtype', None) == 'cumulus':
            mlagDualPortsCnt = 0
            mlagSinglePortsCnt = 0
            mlagErrorPortsCnt = 0
            mlagDualPorts = []
            mlagSinglePorts = []
            mlagErrorPorts = []

            for entry in processed_data:
                mlagIfs = entry['mlagInterfaces']
                for mlagif in mlagIfs:
                    if mlagIfs[mlagif]['status'] == 'dual':
                        mlagDualPortsCnt += 1
                        mlagDualPorts.append(mlagif)
                    elif mlagIfs[mlagif]['status'] == 'single':
                        mlagSinglePortsCnt += 1
                        mlagSinglePorts.append(mlagif)
                    elif (mlagIfs[mlagif]['status'] == 'errDisabled' or
                          mlagif['status'] == 'protoDown'):
                        mlagErrorPortsCnt += 1
                        mlagErrorPorts.append(mlagif)
                entry['mlagDualPorts'] = mlagDualPorts
                entry['mlagSinglePorts'] = mlagSinglePorts
                entry['mlagErrorPorts'] = mlagErrorPorts
                entry['mlagSinglePortsCnt'] = mlagSinglePortsCnt
                entry['mlagDualPortsCnt'] = mlagDualPortsCnt
                entry['mlagErrorPortsCnt'] = mlagErrorPortsCnt
                del entry['mlagInterfaces']

        return super().clean_data(processed_data, raw_data)


class OspfIfService(Service):
    '''OSPF Interface service. Output needs to be munged'''

    def clean_data(self, processed_data, raw_data):

        if raw_data.get('devtype', None) == 'cumulus':
            for entry in processed_data:
                entry['vrf'] = 'default'
                entry['networkType'] = entry['networkType'].lower()
        elif raw_data.get('devtype', None) == 'eos':
            for entry in processed_data:
                entry['networkType'] = entry['networkType'].lower()

        return super().clean_data(processed_data, raw_data)


class OspfNbrService(Service):
    '''OSPF Neighbor service. Output needs to be munged'''

    def frr_convert_reltime_to_epoch(self, reltime):
        '''Convert string of type 1d12h3m23s into absolute epoch'''
        secs = 0
        s = reltime
        for t, mul in {'d': 3600*24, 'h': 3600, 'm': 60, 's': 1}.items():
            v = s.split(t)
            if len(v) == 2:
                secs += int(v[0])*mul
            s = v[-1]

        return int((time.time() - secs)*1000)

    def clean_data(self, processed_data, raw_data):

        if raw_data.get('devtype', None) == 'cumulus':
            for entry in processed_data:
                entry['vrf'] = 'default'
                entry['state'] = entry['state'].lower()
                entry['lastChangeTime'] = self.frr_convert_reltime_to_epoch(
                    entry['lastChangeTime'])
        elif raw_data.get('devtype', None) == 'eos':
            for entry in processed_data:
                entry['state'] = entry['state'].lower()
                entry['lastChangeTime'] = int(entry['lastChangeTime']*1000)

        return super().clean_data(processed_data, raw_data)
