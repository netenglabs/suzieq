
import os
import sys
import re
from datetime import datetime
from pathlib import Path
import logging
import json
from collections import OrderedDict

import yaml
import typing
import pandas as pd

sys.path.append('/home/ddutt/work/')
from suzieq.livylib import get_livysession, exec_livycode

code_tmpl = '''
import sys
import datetime
sys.path.append("/home/ddutt/work/")
from suzieq.utils import get_latest_files

files = dict()
for k in {1}:
    v = get_latest_files("{0}" + "/" + k, start="{3}", end="{4}")
    files[k] = v

for k, v in files.items():
    spark.read.option("basePath", "{0}").load(v).createOrReplaceTempView(k)

x={2}
for k in {1}:
  spark.catalog.dropTempView(k)
x
'''

code_viewall_tmpl = '''
import sys
sys.path.append("/home/ddutt/work/suzieq/")

for k in {1}:
    spark.read.option("basePath", "{0}").load("{0}/" + k).createOrReplaceTempView(k)

x={2}
for k in {1}:
  spark.catalog.dropTempView(k)
x

'''


def validate_sq_config(cfg, fh):
    '''Validate Suzieq config file

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file
    fh:  file logger handle

    Returns:
    --------
    status: None if all is good or error string
    '''

    ddir = cfg.get('data-directory', None)
    if not ddir:
        return('No data directory for output files specified')

    sdir = cfg.get('service-directory', None)
    if not sdir:
        return('No service config directory specified')

    p = Path(sdir)
    if not p.is_dir():
        return('Service directory {} is not a directory'.format(sdir))

    scdir = cfg.get('service-directory', None)
    if not scdir:
        scdir = sdir + '/schema'
        cfg['schema-directory'] = scdir

    p = Path(scdir)
    if not p.is_dir():
        return('Invalid schema directory specified')

    ksrv = cfg.get('kafka-servers', None)
    if ksrv:
        from confluent_kafka import Consumer, KafkaException
        kc = Consumer({'bootstrap.servers': ksrv}, logger=fh)

        try:
            kc.list_topics(timeout=1)
        except KafkaException as e:
            return ('Kafka server error: {}'.format(str(e)))

        kc.close()

    return None


def load_sq_config(validate=True):
    '''Load (and validate) basic suzieq config'''

    # Order of looking up suzieq config:
    #   Current directory
    #   ${HOME}/.suzieq/

    cfgfile = None
    cfg = None

    if os.path.exists('./suzieq-cfg.yml'):
        cfgfile = './suzieq-cfg.yml'
    elif os.path.exists(os.getenv('HOME') + '/.suzieq/suzieq-cfg.yml'):
        cfgfile = os.getenv('HOME') + '/.suzieq/suzieq-cfg.yml'

    if cfgfile:
        with open(cfgfile, 'r') as f:
            cfg = yaml.load(f.read())

        if validate:
            validate_sq_config(cfg, sys.stderr)

    return cfg


def get_latest_files(folder, start='', end=''):
    lsd = []

    def get_latest_ts_dirs(dirs, ssecs, esecs):
        newdirs = None

        if not ssecs and not esecs:
            dirs.sort(key=lambda x: int(x.split('=')[1]))
            newdirs = dirs
        elif ssecs and not esecs:
            newdirs = list(filter(lambda x: int(x.split('=')[1]) > ssecs,
                                  dirs))
            if not newdirs:
                # FInd the entry most adjacent to this one
                newdirs = list(
                    filter(lambda x: int(x.split('=')[1]) < ssecs,
                           dirs))
        elif esecs and not ssecs:
            newdirs = list(filter(lambda x: int(x.split('=')[1]) < esecs,
                                  dirs))
        else:
            newdirs = list(filter(lambda x: int(x.split('=')[1]) < esecs
                                  and int(x.split('=')[1]) > ssecs, dirs))
            if not newdirs:
                # FInd the entry most adjacent to this one
                newdirs = list(
                    filter(lambda x: int(x.split('=')[1]) < ssecs,
                           dirs))

        return newdirs

    def get_latest_pq_files(files, root, ssecs, esecs):

        newfiles = None

        if not ssecs and not esecs:
            files.sort(key=lambda x: os.path.getctime(
                '%s/%s' % (root, x)))
            newfiles = files
        elif ssecs and not esecs:
            newfiles = list(filter(
                lambda x: os.path.getctime('%s/%s' % (root, x)) > ssecs,
                files))
            if not newfiles:
                # FInd the entry most adjacent to this one
                newfiles = list(filter(
                    lambda x: os.path.getctime('%s/%s' % (root, x)) > ssecs,
                    files))
        elif esecs and not ssecs:
            newfiles = list(filter(
                lambda x: os.path.getctime('%s/%s' % (root, x)) < esecs,
                files))
        else:
            newfiles = list(filter(
                lambda x: os.path.getctime('%s/%s' % (root, x)) < esecs
                and os.path.getctime('%s/%s' % (root, x)) > ssecs, files))
            if not newfiles:
                # Find the entry most adjacent to this one
                newfiles = list(filter(
                    lambda x: os.path.getctime('%s/%s' % (root, x)) > ssecs,
                    files))
        return newfiles

    if start:
        tmp = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
        ssecs = int(tmp.strftime('%s')*1000)
    else:
        ssecs = 0

    if end:
        tmp = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
        esecs = int(tmp.strftime('%s')*1000)
    else:
        esecs = 0

    ts_dirs = False
    pq_files = False
    for root, dirs, files in os.walk(folder):
        flst = None
        if dirs and dirs[0].startswith('timestamp') and not pq_files:
            flst = get_latest_ts_dirs(dirs, ssecs, esecs)
            ts_dirs = True
        elif files and not ts_dirs:
            flst = get_latest_pq_files(files, root, ssecs, esecs)
            pq_files = True

        if flst:
            lsd.append(os.path.join(root, flst[-1]))

    return lsd


def get_schemas(schema_dir):

    schemas = {}

    if not os.path.exists(schema_dir):
        logging.error('Schema directory {} does not exist'.format(schema_dir))
        return schemas

    for root, _, files in os.walk(schema_dir):
        for topic in files:
            with open(root + '/' + topic, 'r') as f:
                data = json.loads(f.read())
                schemas[data['name']] = data['fields']
        break

    return schemas


def get_table_df(table: str, start_time: str, end_time: str,
                 view: str, order_by: str, cfg, schemas,
                 **kwargs):
    '''Build query string and get dataframe'''

    qstr = build_sql_str(table, start_time, end_time, view,
                         order_by, schemas, **kwargs)
    if not qstr:
        return None

    df = get_query_output(qstr, cfg, schemas,
                          start_time, end_time, view)
    return df


def build_sql_str(table: str, start_time: str, end_time: str,
                  view: str, order_by: str, schemas, **kwargs):
    '''Workhorse routine to build the actual SQL query string'''

    sch = schemas.get(table)
    if not sch:
        print('Unknown table {}, no schema found for it'.format(table))
        return ''

    fields = []
    wherestr = ''
    if 'columns' in kwargs:
        columns = kwargs['columns']
        del kwargs['columns']
    else:
        columns = 'default'

    if columns == 'default':
        for field in sch:
            loc = field.get('display', None)
            if loc is not None:
                fields.insert(loc, field['name'])

        if 'timestamp' not in fields:
            fields.append('from_unixtime(timestamp/1000) as timestamp')
    else:
        fields = ['*']

    first = True
    for i, kwd in enumerate(kwargs):
        if not kwargs[kwd]:
            continue

        if first:
            prefix = 'where'
            first = False
        else:
            prefix = 'and'
        value = kwargs[kwd]

        if isinstance(value, list):
            kwdstr = ''
            for j, e in enumerate(value):
                prefix1 = ' or' if j else '('
                kwdstr += "{} {} == '{}'".format(prefix1, kwd, e)
            kwdstr += ')'
        else:
            kwdstr = " {}=='{}'".format(kwd, value)

        wherestr += " {} {}".format(prefix, kwdstr)

    if view != 'latest':
        timestr = ''
        if start_time:
            timestr = (" and timestamp(timestamp/1000) > timestamp('{}')"
                       .format(start_time))
        if end_time:
            timestr += (" and timestamp(timestamp/1000) < timestamp('{}') "
                        .format(end_time))
        if timestr:
            wherestr += timestr
        order_by = 'order by timestamp'

    output = 'select {} from {} {} {}'.format(', '.join(fields), table,
                                              wherestr, order_by)
    return output


def get_spark_code(qstr: str, cfg, schemas, start: str = '', end: str = '',
                   view: str ='latest') -> str:
    '''Get the Table creation and destruction code for query string'''

    # SQL syntax has keywords separated by space, multiple values for a keyword
    # separated by comma.
    qparts = re.split(r'(?<!,)\s+', qstr)
    tables = []
    counter = []

    if counter or view == 'all':
        # We need to apply time window to sql
        windex = [i for i, x in enumerate(qparts) if x.lower() == "where"]
        timestr = '('
        if start:
            ssecs = int(datetime.strptime(start, '%Y-%m-%d %H:%M:%S').strftime('%s'))*1000
            timestr += "timestamp > {} ".format(ssecs)
        if end:
            esecs = int(datetime.strptime(end, '%Y-%m-%d %H:%M:%S').strftime('%s'))*1000
            if timestr != '(':
                timestr += (
                    " and timestamp < {})".format(esecs))
            else:
                timestr += ("(timestamp < {})".format(esecs))
        if timestr:
            if windex:
                timestr += ' and '
                qparts.insert(windex[0]+1, timestr)
            else:
                timestr = ' where {}'.format(timestr)

    qstr = ' '.join(qparts)

    indices = [i for i, x in enumerate(qparts) if x.lower() == "from"]
    indices += [i for i, x in enumerate(qparts) if x.lower() == "join"]

    print(qstr)
    for index in indices:
        words = re.split(r',\s*', qparts[index+1])
        for table in words:
            if table in schemas:
                tables.append(table)

    sstr = 'spark.sql("{0}").toJSON().collect()'.format(qstr)
    if view == 'latest':
        code = code_tmpl.format(cfg['data-directory'], tables, sstr,
                                start, end)
    else:
        code = code_viewall_tmpl.format(cfg['data-directory'], tables,
                                        sstr)
    return code


def get_query_output(query_string: str, cfg, schemas,
                     start_time: str = '', end_time: str ='',
                     view: str = 'latest') -> pd.DataFrame:

    df = None

    try:
        session_url = get_livysession()
    except Exception:
        session_url = None

    if not session_url:
        print('Unable to find valid, active Livy session')
        print('Queries will not execute')
        return df

    query_string = query_string.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query_string.split()
    if "'" in words[-1] and not re.search(r"'(?=')?", words[-1]):
        words[-1] += "'"
        query_string = ' '.join(words)

    code = get_spark_code(query_string, cfg, schemas, start_time, end_time,
                          view)
    output = exec_livycode(code, session_url)
    if output['status'] != 'ok':
        df = {'error': output['status'],
              'type': output['ename'],
              'errorMsg': output['evalue'].replace('\\n', ' ')
                                          .replace('u\"', '')}
    else:
        # We don't use read_json because that call doesn't preserve column
        # order.
        jout = json.loads(output['data']['text/plain']
                          .replace("\', u\'", ', ')
                          .replace("u\'", '')
                          .replace("\'", ''), object_pairs_hook=OrderedDict)
        df = pd.DataFrame.from_dict(jout)

    if df is not None and '__index_level_0__' in df.columns:
        df = df.drop(columns=['__index_level_0__'])

    return df


def get_ifbw_df(datacenter: typing.List[str], hostname: typing.List[str],
                ifname: typing.List[str], columns: typing.List[str],
                start_time: str, end_time: str, cfg, schemas):
    '''Return a DF for interface bandwidth for specified hosts/ifnames'''

    if isinstance(ifname, str) and ifname:
        ifname = [ifname]

    if isinstance(hostname, str) and hostname:
        hostname = [hostname]

    if isinstance(datacenter, str) and datacenter:
        datacenter = [datacenter]

    if ifname:
        ifname_str = '('
        for i, ele in enumerate(ifname):
            prefix = ' or ' if i else ''
            ifname_str += "{}ifname=='{}'".format(prefix, ele)

        ifname_str += ')'
    else:
        ifname_str = ''

    if hostname:
        hostname_str = '('
        for i, ele in enumerate(hostname):
            prefix = ' or ' if i else ''
            hostname_str += "{}hostname=='{}'".format(prefix, ele)
        hostname_str += ')'
    else:
        hostname_str = ''

    if datacenter:
        dc_str = '('
        for i, ele in enumerate(datacenter):
            prefix = ' or ' if i else ''
            dc_str += "{}datacenter=='{}'".format(prefix, ele)
        dc_str += ')'
    else:
        dc_str = ''

    wherestr = ''
    for wstr in [dc_str, hostname_str, ifname_str]:
        if wstr:
            if wherestr:
                wherestr += ' and '
            else:
                wherestr += 'where '

            wherestr += wstr

    qstr = ("select datacenter, hostname, ifname, {}, timestamp "
            "from ifCounters {} order by datacenter, hostname, ifname, "
            "timestamp".format(', '.join(columns), wherestr))

    df = get_query_output(qstr, cfg, schemas, start_time, end_time, view='all')
    for col_name in columns:
        df['prevBytes(%s)' % (col_name)] = df.groupby(
            ['datacenter', 'hostname', 'ifname'])[col_name].shift(1)

    idflist = []
    for dele in datacenter:
        for hele in hostname:
            for iele in ifname:
                dflist = []
                for col_name in columns:
                    subdf = df.where((df['datacenter'] == dele) &
                                     (df['hostname'] == hele) &
                                     (df['ifname'] == iele))\
                                     [['datacenter', 'hostname', 'ifname',
                                       col_name, 'timestamp',
                                       'prevBytes(%s)' % col_name]]
                    subdf = subdf.dropna()
                    subdf['prevTime'] = subdf.groupby(
                        ['datacenter', 'hostname', 'ifname'])['timestamp'].shift(1)
                    subdf['rate(%s)' % col_name] = (
                        (subdf[col_name].sub(subdf['prevBytes(%s)' % (col_name)])
                         * 8 / (subdf['timestamp'].sub(subdf['prevTime']))))
                    subdf['timestamp'] = pd.to_datetime(subdf['timestamp'],
                                                        unit='ms')
                    dflist.append(subdf.drop(columns=[col_name,
                                                      'prevBytes(%s)' % (col_name),
                                                      'prevTime']))

                if len(dflist) > 1:
                    newdf = dflist[0]
                    for i, subdf in enumerate(dflist[1:]):
                        newdf = pd.merge(newdf,
                                         subdf[['rate(%s)' % (columns[i+1]),
                                                'timestamp']],
                                         on='timestamp', how='left')
                else:
                    newdf = dflist[0]

                idflist.append(newdf)

    if len(idflist) > 1:
        newdf = idflist[0]
        for i, subdf in enumerate(idflist[1:]):
            newdf = pd.concat([newdf, subdf])
    else:
        newdf = idflist[0]

    return newdf
