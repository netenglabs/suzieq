
from collections import defaultdict
import asyncio
import random
import time
import re
import ast
import json
import copy
import logging

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from fastavro.validation import validate_many
import textfsm


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
            fkeys = re.split(r'([,+*/])', okeys[1])
            if len(fkeys) > 1:
                rval = None
                fkeys = [fkeys[0].strip(), fkeys[1], fkeys[2].strip()]
                if fkeys[2] not in oresult:
                    if not fkeys[2].isdigit():
                        # This is an unsuppported operation, need int field
                        oresult[fkeys[0]] = 0
                        return
                    else:
                        rval = int(fkeys[2])
                else:
                    rval = int(oresult[fkeys[2]])
                if fkeys[1] == '+':
                    oresult[fkeys[0]] = indata.get(okeys[0], 0) + rval
                elif fkeys[1] == '-':
                    oresult[fkeys[0]] = indata.get(okeys[0], 0) - rval
                elif fkeys[1] == '*':
                    oresult[fkeys[0]] = indata.get(okeys[0], 0) * rval
                elif fkeys[1] == '/':
                    if rval:
                        oresult[fkeys[0]] = indata.get(okeys[0], 0) / rval
                    else:
                        oresult[fkeys[0]] = 0
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
    try:
        template = open(fsm_template)
    except IOError as e:
        logging.error('Unable to open textfsm template {}, error:{}'.format(
            fsm_template, e))
        return records

    re_table = textfsm.TextFSM(template)
    res = re_table.ParseText(raw_input)

    fields = {v['name']: i
              for i, v in enumerate(schema['fields'])}

    ptype_map = {'string': str,
                 'int': int,
                 'long': int,
                 'double': float,
                 'array': list,
                 'map': dict,
                 'boolean': bool
                 }

    # Ensure the type is set correctly.
    for entry in res:
        metent = dict(zip(re_table.header, entry))
        for cent in metent:
            if cent in fields:
                schent_type = schema['fields'][fields[cent]]['type']
                sch_type = schent_type if type(schent_type) == str \
                    else schent_type['type'] \
                    if type(schent_type) == dict \
                    else schent_type['type'][0]
                if type(metent[cent]) != ptype_map[sch_type]:
                    metent[cent] = ptype_map[sch_type](metent[cent])

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

    def __init__(self, name, defn, keys, ignore_fields, schema, output_dir):
        self.name = name
        self.defn = defn
        self.ignore_fields = ignore_fields
        self.output_dir = output_dir
        self.keys = keys
        self.schema = schema

        self.logger = logging.getLogger('suzieq')

        # Add the hidden fields to ignore_fields
        self.ignore_fields.append('active')
        self.ignore_fields.append('timestamp')

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
                    tfsm_template = nfn.get('textfsm', '')
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
        def_vals = {'string': '-', 'int': 0, 'long': 0, 'double': 0,
                    'array': [], 'map': {}, 'boolean': False}
        for field in self.schema['fields']:
            default = def_vals.get(field['type'], '') \
                      if type(field['type']) == str \
                      else def_vals.get(field['type']['type'], '') \
                      if type(field['type']) == dict \
                      else def_vals.get(field['type'][0])

            schema_rec.update({field['name']: default})

        for entry in processed_data:
            entry.update({'hostname': raw_data['hostname']})
            entry.update({'timestamp': raw_data['timestamp']})
            for fld in schema_rec:
                if fld not in entry:
                    entry.update({fld: schema_rec[fld]})

        validate_many(processed_data, self.schema)

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
                df = pd.DataFrame.from_dict(records)
                table = pa.Table.from_pandas(df)
                pq.write_to_dataset(
                    table,
                    root_path='{}/{}/{}'.format(self.output_dir,
                                                datacenter,
                                                self.name),
                    partition_cols=['timestamp'],
                    flavor='spark')

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
        if raw_data.get('devtype', None) == 'eos':
            for entry in processed_data:
                # Fixup speed:
                new_list = []
                entry['speed'] = str(int(entry['speed']/1000000000)) + 'G'

                tmpent = entry.get('ipAddressList', [[]])
                if not tmpent:
                    continue
                munge_entry = tmpent[0]
                if munge_entry:
                    primary_ip = (
                        munge_entry['primaryIp']['address'] + '/' +
                        str(munge_entry['primaryIp']['maskLen'])
                    )
                    new_list.append(primary_ip)
                    for elem in munge_entry['secondaryIpsOrderedList']:
                        ip = elem['adddress'] + '/' + elem['maskLen']
                        new_list.append(ip)

                munge_entry = entry.get('ip6AddressList', [{}])
                if munge_entry:
                    for elem in munge_entry[0].get('globalUnicastIp6s', []):
                        new_list.append(elem['subnet'])

                entry['ipAddressList'] = new_list
                if 'ip6AddressList' in entry:
                    del entry['ip6AddressList']

        super(InterfaceService, self).clean_data(processed_data, raw_data)

        return


class SystemService(Service):
    '''Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    '''

    def __init__(self, name, defn, keys, ignore_fields, schema, output_dir):
        super(SystemService, self).__init__(name, defn, keys, ignore_fields,
                                            schema, output_dir)
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

