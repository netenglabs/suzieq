import sys
import qgrid
import pandas as pd
import json
import warnings
import os
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

sys.path.append("/home/ddutt/work/suzieq/")

from livylib import get_livysession, exec_livycode

is_notebook = False
qgrid_enable = True


def get_latest_df(folder):
    lsd = []

    for root, dirs, files in os.walk(folder):
        if dirs and dirs[0].startswith('timestamp'):
            dirs.sort()
            lsd.append(os.path.join(root, dirs[-1]))

    pdf_list = []
    for file in lsd:
        df = pd.read_parquet(file)
        p = Path(file).parts
        for elem in p:
            if '=' in elem:
                k, v = elem.split('=')
                df[k] = v
        pdf_list.append(df)

    if pdf_list:
        final_df = pd.concat(pdf_list)
    else:
        final_df = None

    return final_df


def get_df_for_window(folder, start=None, end=None):

    if not start and not end:
        return get_latest_df(folder)
    elif start and not end:
        timeset = pd.date_range(pd.to_datetime(start), periods=2, freq='15min')
    elif end and not start:
        timeset = pd.date_range(end=pd.to_datetime(end), periods=2, freq='15min')
    else:
        timeset = [pd.to_datetime(start), pd.to_datetime(end)]

    table = pq.ParquetDataset(folder,
                              filters=[('timestamp', '>', timeset[0]),
                                       ('timestamp', '<', timeset[-1])]) \
              .read()

    df = table.to_pandas()

    return df


def query(qstr):
    '''Send query string to Livy server and receive HTML output back'''

    global session_url

    grid_options = {'minVisibleRows': 1, 'maxVisibleRows': 50}

    # Replace any double quoted strings to single quotes first
    qstr.replace("'", '"')

    if is_notebook:
        if qgrid_enable:
            sstr = 'spark.sql("{0}").toJSON().collect()'.format(qstr)
        else:
            sstr = 'spark.sql("{0}").toPandas().to_html()'.format(qstr)
    else:
        sstr = 'spark.sql("{0}").show()'.format(qstr)

    output = exec_livycode(sstr, session_url)
    if is_notebook:
        if qgrid_enable:
            jout = output['data']['text/plain']
            return qgrid.show_grid(pd.read_json(
                jout.replace("\', u\'", ', ').replace("u\'", '')
                .replace("\'", ''), orient='frame'),
                grid_options=grid_options)
        return display(HTML(output['data']['text/plain']
                            .replace('\\n', ' ')
                            .replace("u\'", '')[:-1]))
    else:
        print(output['data']['text/plain']
              .replace('\\n', ' ')
              .replace("u\'", ''))
    return


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


if 'ipykernel' in str(type(get_ipython())):
    is_notebook = True

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
