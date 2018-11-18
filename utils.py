
import os
import sys
import re
from datetime import datetime
from pathlib import Path
import logging
import json
from collections import OrderedDict

import yaml
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

counter_code_tmpl = '''
import pyspark.sql.functions as F
from pyspark.sql.window import Window

for k in {1}:
    spark.read.option("basePath", "{0}").load("{0}/" + k).createOrReplaceTempView(k)

cntrdf={2}

col_name = "{3}"
cntrdf = cntrdf \
             .withColumn('prevTime',
                         F.lag(cntrdf.timestamp).over(Window.partitionBy()
                                                      .orderBy('timestamp')))
cntrdf = cntrdf \
             .withColumn('prevBytes',
                         F.lag(col_name).over(Window.partitionBy()
                                              .orderBy('timestamp')))

cntrdf = cntrdf \
             .withColumn("rate",
                         F.when(F.isnull(F.col(col_name) - cntrdf.prevBytes), 0)
                         .otherwise((F.col(col_name) - cntrdf.prevBytes)*8 /
                                    (cntrdf.timestamp.astype('double')-cntrdf.prevTime.astype('double')))) \
             .drop('prevTime', 'prevBytes')

for k in {1}:
  spark.catalog.dropTempView(k)

cntrdf.toJSON().collect()
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

    for root, dirs, files in os.walk(folder):
        flst = None
        if dirs and dirs[0].startswith('timestamp'):
            flst = get_latest_ts_dirs(dirs, ssecs, esecs)
        elif files:
            flst = get_latest_pq_files(files, root, ssecs, esecs)

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


def get_spark_code(qstr: str, cfg, schemas, start: str = '', end: str = '',
                   view: str ='latest') -> str:
    '''Get the Table creation and destruction code for query string'''

    # SQL syntax has keywords separated by space, multiple values for a keyword
    # separated by comma.
    qparts = re.split(r'(?<!,)\s+', qstr)
    tables = []
    counter = None

    # Check if any of the select columns have a rate field
    if qparts[0] == 'select':
        fields = re.split(r',\s*', qparts[1])
        newfields = []
        for field in fields:
            if 'rate(' in field:
                mstr = re.match(r'rate\s*\(\s*(\s*\w+\s*)\s*\)', field)
                if mstr:
                    counter = mstr[1]
                    newfields.append(counter)
            else:
                newfields.append(field)

        qparts[1] = ', '.join(newfields)

    if counter:
        # We need to apply time window to sql
        windex = [i for i, x in enumerate(qparts) if x.lower() == "where"]
        timestr = ("timestamp(timestamp/1000) > timestamp('{}') and "
                   "timestamp(timestamp/1000) < timestamp('{}') and ".format(start, end))
        qparts.insert(windex[0]+1, timestr)

    qstr = ' '.join(qparts)

    indices = [i for i, x in enumerate(qparts) if x.lower() == "from"]
    indices += [i for i, x in enumerate(qparts) if x.lower() == "join"]

    for index in indices:
        words = re.split(r',\s*', qparts[index+1])
        for table in words:
            if table in schemas:
                tables.append(table)

    if counter:
        sstr = 'spark.sql("{0}")'.format(qstr)
        cprint(sstr)
        code = counter_code_tmpl.format(cfg['data-directory'], tables,
                                        sstr, counter)
    else:
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

    try:
        session_url = get_livysession()
    except Exception:
        session_url = None

    if not session_url:
        print('Unable to find valid, active Livy session')
        print('Queries will not execute')
        return

    query_string = query_string.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query_string.split()
    if "'" in words[-1] and not re.search(r"'(?=')", words[-1]):
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

    return df
