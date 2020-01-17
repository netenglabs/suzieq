import sys
import qgrid
import json
import warnings
import re
from pathlib import Path
from collections import defaultdict

import pandas as pd

from IPython.display import display

sys.path.append("/home/ddutt/work/suzieq/")

from suzieq.utils import load_sq_config, get_schemas, get_query_df
from suzieq.livylib import get_livysession, exec_livycode

is_notebook = False
qgrid_enable = True
cfg = defaultdict(lambda: '')
schemas = defaultdict(lambda: [])


def query(qstr):
    '''Send query string to Livy server and receive HTML output back'''

    global session_url

    grid_options = {'minVisibleRows': 1, 'maxVisibleRows': 50}

    # Replace any double quoted strings to single quotes first
    qstr.replace("'", '"')
    qstr = qstr.strip()
    dfolder = cfg['data-directory']

    if qstr == 'show tables':
        if dfolder:
            p = Path(dfolder)
            tables = [{'table': dir.parts[-1]} for dir in p.iterdir()
                      if dir.is_dir() and not dir.parts[-1].startswith('_')]
            df = pd.DataFrame.from_dict(tables)
    elif qstr.startswith('describe table'):
        words = re.split(r'describe table\s+', qstr)
        if len(words) > 1 and words[1].strip():
            words = words[1].strip()
            if re.search(r'\s+', words):
                table = words.split()[0]
            else:
                table = words
            entries = [{'name': x['name'], 'type': x['type']}
                       for x in schemas[table]]
            df = pd.DataFrame.from_dict(entries)
        else:
            df = pd.DataFrame.from_dict({'error': 'Invalid command'})
    else:
        df = get_query_df(qstr, cfg, schemas)

    if is_notebook:
        if qgrid_enable:
            return qgrid.show_grid(df, grid_options=grid_options)
        else:
            return display(df.style)
    else:
        print(df)


def lpm(saddr, host='.*'):
    '''Return routing table lookup for entries'''

    return


def get_list_from_spark(code, session_url, key):
    '''Returns list collected from the list produced by the code
    This doesn't do any checking for now
    '''
    output = exec_livycode(code, session_url)
    if output.get('status', 'error') == 'ok':
        data = json.loads(output['data']['text/plain']
                          .replace("\', u\'", ', ')
                          .replace("u\'", '')
                          .replace("\'", ''))
        return [x[key] for x in data]
    return []


def get_hostlist(session_url):
    '''Get the list of all hosts in the DB'''
    return get_list_from_spark(
        '''spark.sql("select distinct host from link").toJSON().collect()''',
        session_url, 'host')


def get_iflist(session_url, host='.*'):
    '''Get the list of interfaces asssociated with the given host'''
    return get_list_from_spark(
        '''spark.sql("select distinct ifname from link where host regexp '{0}'").toJSON().collect()'''.format(host),
        session_url, 'ifname')


def get_vrflist(session_url, host='.*'):
    '''Get the list of interfaces asssociated with the given host'''
    return get_list_from_spark(
        '''spark.sql("select distinct ifname from link where type == 'vrf' and host regexp '{0}'").toJSON().collect()'''.format(host), session_url, 'ifname')


if __name__ == '__main__':
    if 'ipykernel' in str(type(get_ipython())):
        is_notebook = True

    cfg = load_sq_config()

    schemas = get_schemas(cfg['schema-directory'])

    try:
        session_url = get_livysession()
    except Exception:
        session_url = None

    if not session_url:
        print('Unable to find valid, active Livy session')
        print('Queries will not execute')

    # Need this for jupyter notebook
    warnings.filterwarnings("ignore", message="numpy.dtype size changed")
    warnings.filterwarnings("ignore", message="numpy.ufunc size changed")


