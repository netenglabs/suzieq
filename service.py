
from collections import defaultdict
import os
import asyncio
import random
import time
import re
import ast
import json

import yaml
import copy
import logging

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import textfsm
from pyarrow import DataType
from pyarrow.lib import Field


def avro_to_arrow_schema(avro_sch):
    '''Given an AVRO schema, return the equivalent Arrow schema'''
    arsc_fields = []

    map_type = {'string': pa.string(),
                'long': pa.int64(),
                'int': pa.int32(),
                'double': pa.float64(),
                'timestamp': pa.date64(),
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


async def init_services(svc_dir, schema_dir, output_dir):
    '''Process service definitions by reading each file in svc dir'''

    svcs_list = []
    if not os.path.isdir(svc_dir):
        logging.error('services directory not a directory: {}', svc_dir)
        return svcs_list

    if not os.path.isdir(schema_dir):
        logging.error('schema directory not a directory: {}', svc_dir)
        return svcs_list

    for root, dirnames, filenames in os.walk(svc_dir):
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
                    if ('command' not in val or
                            ('normalize' not in val and 'textfsm' not in val)):
                        logging.error('Ignorning invalid service file definition. \
                        Need both "command" and "normalize/textfsm" keywords:'
                                      '{}, {}'.format(filename, val))
                        continue

                    if 'textfsm' in val:
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
                                               schema, output_dir)
                elif svc_def['service'] == 'system':
                    service = SystemService(svc_def['service'],
                                            svc_def['apply'],
                                            period,
                                            svc_def.get('type', 'state'),
                                            svc_def.get('keys', []),
                                            svc_def.get('ignore-fields', []),
                                            schema, output_dir)
                elif svc_def['service'] == 'mlag':
                    service = MlagService(svc_def['service'],
                                          svc_def['apply'],
                                          period,
                                          svc_def.get('type', 'state'),
                                          svc_def.get('keys', []),
                                          svc_def.get('ignore-fields', []),
                                          schema, output_dir)
                else:
                    service = Service(svc_def['service'], svc_def['apply'],
                                      period, svc_def.get('type', 'state'),
                                      svc_def.get('keys', []),
                                      svc_def.get('ignore-fields', []),
                                      schema, output_dir)

                logging.info('Service {} added'.format(service.name))
                svcs_list.append(service)

    return svcs_list


def exdict(path, data, start, collect=False):
    '''Extract all fields in specified path from data'''

    def set_kv(okeys, indata, oresult):
        '''Set the value in the outgoing dict'''
        if okeys:
            okeys = [okeys[0].strip(), okeys[1].strip()]
        if '?' in okeys[1]:
            fkey, fvals = okeys[1].split('?')
            fvals = fvals.split('|')
            cval = indata.get(okeys[0], '')
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
            if not cval or (tval and str(cval) != tval):
                try:
                    oresult[fkey.strip()] = ast.literal_eval(fvals[1])
                except (ValueError, SyntaxError):
                    oresult[fkey.strip()] = fvals[1]
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
                if op == 'add':
                    oresult[lval] = indata.get(okeys[0], 0) + rval
                elif op == 'sub':
                    oresult[lval] = indata.get(okeys[0], 0) - rval
                elif op == 'mul':
                    oresult[lval] = indata.get(okeys[0], 0) * rval
                elif op == 'div':
                    if rval:
                        oresult[lval] = indata.get(okeys[0], 0) / rval
                    else:
                        oresult[lval] = 0
            else:
                rval = indata.get(okeys[0], '')
                try:
                    oresult[okeys[1].strip()] = ast.literal_eval(rval)
                except (ValueError, SyntaxError):
                    oresult[okeys[1].strip()] = rval
        return

    result = []
    iresult = {}

    plist = re.split('''/(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', path)
    for i, elem in enumerate(plist[start:]):

        if not data:
            if '[' not in plist[-1] and ':' in plist[-1]:
                set_kv(plist[-1].split(':'), data, iresult)
                result.append(iresult)
            return result, i+start

        j = 0
        num = re.match('\[([0-9]*)\]', elem)
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
                    tmpres, j = exdict(path, datum, start+i+1)
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
                if i+1 == len(plist):
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
                            sresult, _ = exdict(fld, data, 0, collect=True)
                            for res in sresult:
                                iresult.update(res)
                        else:
                            okeys = fld.split(':')
                            set_kv(okeys, data, iresult)
                    result.append(iresult)
                    iresult = {}

    return result, i+start


def textfsm_data(raw_input, fsm_template, schema):
    '''Convert unstructured output to structured output'''

    records = []
    fsm_template.Reset()
    res = fsm_template.ParseText(raw_input)

    fields = [fld.name for fld in schema]

    ptype_map = {pa.string(): str,
                 pa.int32(): int,
                 pa.int64(): int,
                 pa.float64(): float,
                 pa.date64(): float,
                 pa.list_(pa.string()): list,
                 pa.bool_(): bool
                 }

    map_defaults = {
        pa.string(): '',
        pa.int32(): 0,
        pa.int64(): 0,
        pa.float64(): 0.0,
        pa.date64(): 0.0,
        pa.bool_(): False,
        pa.list_(pa.string()): [],
        pa.list_(pa.int64()): [],
        }

    # Ensure the type is set correctly.
    for entry in res:
        metent = dict(zip(fsm_template.header, entry))
        for cent in metent:
            if cent in fields:
                schent_type = schema.field_by_name(cent).type
                if type(metent[cent]) != ptype_map[schent_type]:
                    if metent[cent]:
                        metent[cent] = ptype_map[schent_type](metent[cent])
                    else:
                        metent[cent] = map_defaults[schent_type]

        records.append(metent)

    return records


class Service(object):
    name = None
    defn = None
    period = 15                 # 15s is the default period
    update_nodes = False
    output_dir = None
    nodes = {}
    new_nodes = {}
    ignore_fields = []
    keys = []
    stype = 'state'

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 output_dir):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields
        self.output_dir = output_dir
        self.keys = keys
        self.schema = schema
        self.period = period
        self.stype = stype

        self.logger = logging.getLogger('suzieq')

        # Add the hidden fields to ignore_fields
        self.ignore_fields.append('active')
        self.ignore_fields.append('timestamp')

        if 'hostname' not in self.keys:
            self.keys.insert(0, 'hostname')

    def set_nodes(self, nodes):
        '''New node list for this service'''
        if self.nodes:
            self.new_nodes = copy.deepcopy(nodes)
            update_nodes = True
        else:
            self.nodes = copy.deepcopy(nodes)

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

        return adds, dels

    async def gather_data(self):
        '''Collect data invoking the appropriate get routine from nodes.'''

        random.shuffle(self.nodelist)
        tasks = [self.nodes[key].exec_service(self.defn)
                 for key in self.nodelist if self.nodes[key].is_alive()]

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
                if nfn.get('normalize', None):
                    if type(data['data']) is str:
                        try:
                            input = json.loads(data['data'])
                        except json.JSONDecodeError as e:
                            logging.error('Received non-JSON output where '
                                          'JSON was expected for {} on node '
                                          '{}, {}'.format(data['cmd'],
                                                          data['hostname'],
                                                          data['data']))
                            return result
                    else:
                        input = data['data']

                    result, _ = exdict(nfn.get('normalize', ''), input, 0)
                else:
                    tfsm_template = nfn.get('textfsm', None)
                    if not tfsm_template:
                        return result

                    if 'output' in data['data']:
                        input = data['data']['output']
                    else:
                        input = data['data']
                    result = textfsm_data(input, tfsm_template, self.schema)

                self.clean_data(result, data)
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
                    pa.float64(): 0, pa.bool_(): False,
                    pa.date64(): 0.0, pa.list_(pa.string()): ['-']}
        for field in self.schema:
            default = def_vals[field.type]
            schema_rec.update({field.name: default})

        for entry in processed_data:
            entry.update({'hostname': raw_data['hostname']})
            entry.update({'timestamp': raw_data['timestamp']})
            for fld in schema_rec:
                if fld not in entry:
                    entry.update({fld: schema_rec[fld]})

    def commit_data(self, result, datacenter, hostname):
        '''Write the result data out'''
        records = []
        if result:
            prev_res = self.nodes.get(hostname, '').prev_result
            adds, dels = self.get_diff(prev_res, result)
            if adds or dels:
                self.nodes.get(hostname, '') \
                          .prev_result = copy.deepcopy(result)
                for entry in adds:
                    entry.update({'active': True})
                    records.append(entry)
                for entry in dels:
                    records.append(entry)

            if records:
                cdir = '{}/{}/{}/'.format(self.output_dir,
                                          datacenter,
                                          self.name)
                if not os.path.isdir(cdir):
                    os.makedirs(cdir)

                df = pd.DataFrame.from_dict(records)
                # pq.write_metadata(
                #     self.schema,'{}/_metadata'.format(cdir),
                #     version='2.0',
                #     coerce_timestamps='us')

                table = pa.Table.from_pandas(df, schema=self.schema)
                pq.write_to_dataset(table, root_path=cdir,
                                    partition_cols=self.keys + ['timestamp'],
                                    version="2.0",
                                    flavor='spark')

                if self.stype == 'state':
                    # Always save the current data wholesome
                    df = pd.DataFrame.from_dict(result)
                    table = pa.Table.from_pandas(df, schema=self.schema)
                    cdir = '{}/{}/current/{}/'.format(self.output_dir,
                                                      datacenter,
                                                      self.name)
                    if not os.path.isdir(cdir):
                        os.makedirs(cdir)
                    pq.write_table(table, '{}/{}.parquet'.format(cdir,
                                                                 hostname),
                                   version='2.0')

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
                self.commit_data(result, output[0]['datacenter'],
                                 output[0]['hostname'])

            if self.update_nodes:
                for node in self.new_nodes:
                    # Copy the last saved outputs to avoid committing dup data
                    if node in self.nodes:
                        new_nodes[node]['output'] = nodes[node]['output']

                nodes = new_nodes
                self.nodelist = list(self.nodes.keys())
                new_nodes = []
                update_nodes = False

            await asyncio.sleep(self.period)


class InterfaceService(Service):
    '''Service class for interfaces. Cleanup of data is specific'''

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
            for entry in processed_data:
                # Fixup speed:
                entry['speed'] = str(int(entry['speed']/1000000000)) + 'G'
                words = entry['master'].split()
                if words:
                    entry['master'] = words[-1].strip()

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

        super(InterfaceService, self).clean_data(processed_data, raw_data)

        return


class SystemService(Service):
    '''Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    '''

    def __init__(self, name, defn, period, stype, keys, ignore_fields,
                 schema, output_dir):
        super(SystemService, self).__init__(name, defn, period, stype, keys,
                                            ignore_fields, schema, output_dir)
        self.ignore_fields.append('bootupTimestamp')

    def clean_data(self, processed_data, raw_data):
        '''Cleanup the bootup timestamp for Linux nodes'''

        devtype = raw_data.get('devtype', None)
        timestamp = raw_data.get('timestamp', time.time())
        for entry in processed_data:
            # We're assuming that if the entry doesn't provide the
            # bootupTimestamp field but provides the sysUptime field,
            # we fix the data so that it is always bootupTimestamp
            # TODO: Fix the clock drift
            if (not entry.get('bootupTimestamp', None) and
                    entry.get('sysUptime', None)):
                entry['bootupTimestamp'] = (
                    raw_data['timestamp'] - float(entry.get('sysUptime')))
                del entry['sysUptime']

        super(SystemService, self).clean_data(processed_data, raw_data)

        return

    def get_diff(self, old, new):

        adds = []
        dels = []
        koldvals = {}
        knewvals = {}
        koldkeys = []
        knewkeys = []

        for i, elem in enumerate(old):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            koldvals.update({tuple(str(vals)): i})

        for i, elem in enumerate(new):
            vals = [v for k, v in elem.items() if k not in self.ignore_fields]
            knewvals.update({tuple(str(vals)): i})

        addlist = [v for k, v in knewvals.items() if k not in koldvals.keys()]
        dellist = [v for k, v in koldvals.items() if k not in knewvals.keys()]

        adds = [new[v] for v in addlist]
        dels = [old[v] for v in dellist if koldkeys[v] not in knewkeys]

        if not (adds or dels):
            # Verify the bootupTimestamp hasn't changed. Compare only int part
            # Assuming no device boots up in millisecs
            if abs(int(new[0]['bootupTimestamp']) != int(old[0]['bootupTimestamp'])) > 2:
                adds.append(new[0])

        return adds, dels


class MlagService(Service):
    '''MLAG service. Different class because output needs to be munged'''

    def clean_data(self, processed_data, raw_data):

        if raw_data.get('devtype', None) == 'cumulus':
            mlagDualPortsCnt = 0
            mlagSinglePortsCnt = 0
            mlagErrorPortsCnt = 0
            mlagPorts = []
            mlagDualPorts = []
            mlagSinglePorts = []
            mlagErrorPorts = []

            for entry in processed_data:
                mlagIfs = entry['mlagInterfaces']
                for mlagif in mlagIfs:
                    if mlagIfs[mlagif]['status'] == 'dual':
                        mlagDualPortsCnt += 1
                        mlagDualPorts.append(mlagif)
                    elif mlagifs[mlagif]['status'] == 'single':
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

        super(MlagService, self).clean_data(processed_data, raw_data)

