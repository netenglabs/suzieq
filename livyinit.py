
import json
import textwrap
import requests
from time import sleep

initcode = """
import sys
import os
from time import sleep, time
import atexit
from shutil import rmtree
import json, textwrap, requests
from multiprocessing import Process, Manager
from threading import Thread
from pathlib import Path

import inotify.adapters

sys.path.append("/home/ddutt/work/suzieq/schema")

from pyspark.sql.functions import col
import schemas

def inotify_process(state, target_dir, notify_refresh):

    i = inotify.adapters.Inotify()
    watch_events = (
        inotify.constants.IN_CREATE | inotify.constants.IN_DELETE |
        inotify.constants.IN_MODIFY | inotify.constants.IN_DELETE_SELF
        )

    dirs = [x for x in Path(target_dir) if x.is_dir()]
    for topic in dirs:
        i.add_watch('{0}/{1}'.format(target_dir, topic), watch_events)

    while True:
        for event in i.event_gen(yield_nones=False):
            (_, type_names, path, filename) = event
            if 'IN_DELETE_SELF' in type_names:
                # This path got deleted, remove it and add it back
                i.add_watch(path, watch_events)
                continue

            state[os.path.basename(path)] = True
            if state['update'] != True:
                state['update'] = True
                with notify_refresh:
                    notify_refresh.notify()

def background_refresh_tables(state, target_dir, notify_refresh,
                              source_dir={0}):

    print 'Background refresh process started'
    while True:
        try:
            with notify_refresh:
                notify_refresh.wait()
        except IOError:
            # Handle this to avoid traceback on exit
            print('Background update exiting on shutdown')
            return

        for topic in schemas.ss_schemas:
            if state.get(topic, False):
                refresh_single_table(topic, spark, source_dir)
                state[topic] = False
            state['update'] = False

def refresh_single_table(topic, spark,
                         datadir={0}):
    '''Refresh the table for a single topic'''

    if not topic or not os.path.isdir(datadir + topic):
        return

    sch = schemas.ss_schemas.get(topic, None)
    if not sch:
        return

    keys = [x.name for x in sch if x.metadata]
    fields = ['last(' + x.name + ') as ' + x.name
              for x in sch if (not x.metadata and
                               x.name not in ['key',  'deleted', 'version'])]

    adf = spark \
          .read \
          .option('mergeSchema', True) \
          .parquet(datadir + topic) \
          .orderBy('timestamp') \

    if topic == 'link':
        adf.filter(col('master').rlike('^[^0-9]'))

    adf.createOrReplaceTempView('a_' + topic)

    selstr = 'select {1}, {2} from a_{0} ' \
             'group by {1}'.format(topic, ', '.join(keys),
                                   ', '.join(fields))

    tdf = spark.sql(selstr) \
               .filter(col('active') == '1') \
               .drop(col('active')) \
               .write \
               .saveAsTable(topic, format='parquet', mode='overwrite',
                            path='/tmp/suzieq/{}'.format(topic))


def refresh_tables():
    '''Build a view that has only the latest data associated with all tables'''

    for topic in schemas.ss_schemas:
        refresh_single_table(topic, spark)

def _main():
    parquet_dir = {0}
    manager = Manager()

    try:
      spark
    except NameError:
      print('Spark session not found')
      return

    if not os.path.exists('/tmp/suzieq'):
        os.mkdir('/tmp/suzieq')


    state = manager.dict({'update': False})
    for topic in schemas.ss_schemas:
        manager.dict({topic: False})

    notify_refresh = manager.Condition()

    notify_proc = Process(target=inotify_process, args=(state, parquet_dir,
                          notify_refresh))
    notify_proc.daemon = True
    notify_proc.start()

    update_proc = Thread(target=background_refresh_tables,
                         args=(state, parquet_dir, notify_refresh))
    update_proc.daemon = True

    refresh_tables()

_main()
"""


def exec_livycode(code, session_url, longer_exec=False,
                  server_url='http://localhost:8998',
                  headers={'Content-Type': 'application/json'}):
    ''' Execute the given string as python code and return result.

    This code blocks until result is available.
    Inputs:
        code: the code to be executed as a string
        session_url: The Spark session_url
        longer_exec: True if this may be a longer running session
        server_url: Livy Server URL
        headers: The headers string to use
    Returns: The raw requests response object
    '''

    data = {'code': textwrap.dedent("""{0} """.format(code))}
    statements_url = session_url + '/statements'

    try:
        r = requests.post(statements_url, data=json.dumps(data),
                          headers=headers)

        joburl = server_url + r.headers['location']
        while True:
            try:
                r = requests.get(joburl, headers=headers)
                if r.json()['state'] == 'available':
                    break
                if longer_exec:
                    sleep(1)
                else:
                    sleep(0.1)             # 100 ms
            except requests.HTTPError:
                print('Unable to get job status of session {}'.format(joburl))
                raise requests.HTTPError
    except requests.HTTPError:
        print('Unable to execute code')
        raise requests.HTTPError

    return r


def get_livysession(server_url='http://localhost:8998'):
    headers = {'Content-Type': 'application/json'}

    return requests.get(server_url + '/sessions', headers=headers)


def get_or_create_livysession(server_url='http://localhost:8998'):
    ''' Create a new pyspark session with Livy REST server, if not existing

        It checks if an existing session with app name suzieq exists and if
        it does, it returns that session URL, else creates a new session and
        returns that info

        Inputs: Livy server URL
        Returns: session ID to use in job submissions, response
    '''

    headers = {'Content-Type': 'application/json'}

    s_response = get_livysession(server_url)
    if s_response.status_code == requests.codes.ok:
        s_json = s_response.json()
        for session in s_json['sessions']:
            session_url = server_url + '/sessions/' + str(session['id'])
            try:
                resp = exec_livycode("""spark.conf.get('spark.app.name')""",
                                     session_url)
                # TODO check valid response code
                appname = resp.json()['output']['data']['text/plain']
                if appname == u"u'suzieq'":
                    return session_url, None
            except requests.HTTPError:
                print('Exception raised by Livy, aborting')
                return None, None

    data = {'kind': 'pyspark', 'conf': {'spark.app.name': 'suzieq'},
            'executorCores': 2}
    r = requests.post(server_url + '/sessions', data=json.dumps(data),
                      headers=headers)
    session_url = server_url + r.headers['location']
    while True:
        s = requests.get(session_url, headers)
        if s.json()['state'] == 'idle':
            return session_url, r


def del_livysession(session_url):
    ''' Deletes the session with the given ID from the Livy Server
        Inputs: Livy Server URL
                Session to delete as returned by create_livysession
        Returns: Response to delete session
    '''

    headers = {'Content-Type': 'application/json'}
    return requests.delete(session_url, headers=headers)


def _main():

    session_url, response = get_or_create_livysession()
    if not session_url:
        # This is in error
        return None
    if not response:
        # We're attaching to an existing Spark session, so carry on
        return session_url

    r = exec_livycode(initcode.format(), session_url, True)
    if r.json()['output']['status'] != 'ok':
        print r.json()
    else:
        print 'All tables created'

    # Need this for jupyter notebook
    import warnings
    warnings.filterwarnings("ignore", message="numpy.dtype size changed")
    warnings.filterwarnings("ignore", message="numpy.ufunc size changed")

    return session_url


if __name__ == '__main__':
    session_url = _main()


