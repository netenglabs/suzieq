
import os
import sys
from datetime import datetime
from pathlib import Path
import logging
import json

import yaml

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

    for root, dirs, _ in os.walk(folder):
        if dirs and dirs[0].startswith('timestamp'):
            dirs.sort(key=lambda x: int(x.split('=')[1]))
            if not ssecs and not esecs:
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

            if newdirs:
                lsd.append(os.path.join(root, newdirs[-1]))

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
