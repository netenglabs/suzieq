import sys
import os
from multiprocessing import Process, Manager
from threading import Thread
from time import sleep

import inotify.adapters

from livylib import get_or_create_livysession, exec_livycode

initcode = """
def refresh_tables(datadir, tmpdir):
    '''Build a view containing only the latest data associated with all tables'''

    for root, dirs, files in os.walk(datadir):
        for topic in dirs:
            refresh_single_table(topic, datadir, tmpdir)
        break

try:
    spark
except NameError:
    print('Spark session not found')

refresh_tables("{0}", "{1}")

"""

refresh_table_code = """
import sys
import os

from pyspark.sql.functions import col

def refresh_single_table(topic, datadir, tmpdir):
    '''Refresh the table for a single topic'''

    if not topic or not os.path.isdir(datadir + topic):
        return

    # keys = [x.name for x in sch if x.metadata]
    # fields = ['last(' + x.name + ') as ' + x.name
    #           for x in sch if (not x.metadata and
    #                            x.name not in ['key',  'deleted', 'version'])]

    adf = spark \
          .read \
          .option('mergeSchema', True) \
          .parquet(datadir + topic) \
          .orderBy('timestamp') \

    # if topic == 'link':
    #     adf.filter(col('master').rlike('^[^0-9]'))

    adf.createOrReplaceTempView('a_' + topic)

    # selstr = 'select {1}, {2} from a_{0} ' \
    #          'group by {1}'.format(topic, ', '.join(keys),
    #                                ', '.join(fields))

    # tdf = spark.sql(selstr) \
    #            .filter(col('active') == '1') \
    #            .drop(col('active')) \
    #            .write \
    #            .saveAsTable(topic, format='parquet', mode='overwrite',
    #                         path='{}/{}'.format(tmpdir, topic))


"""


def inotify_process(state, datadir, notify_refresh):

    i = inotify.adapters.Inotify()
    watch_events = (
        inotify.constants.IN_CREATE | inotify.constants.IN_DELETE |
        inotify.constants.IN_MODIFY | inotify.constants.IN_DELETE_SELF
        )

    for root, dirs, files in os.walk(datadir):
        for topic in dirs:
            i.add_watch('{0}/{1}'.format(root, topic), watch_events)
        break

    while True:
        for event in i.event_gen(yield_nones=False):
            (_, type_names, path, filename) = event
            if 'IN_DELETE_SELF' in type_names:
                # This path got deleted, remove it and add it back
                i.add_watch(path, watch_events)
                continue

            state[os.path.basename(path)] = True
            if state['update'] is False:
                state['update'] = True
                with notify_refresh:
                    notify_refresh.notify()


def background_refresh_tables(state, datadir, notify_refresh, session_url,
                              tmpdir):

    call_func = '\nrefresh_single_table("{0}", "{1}", "{2}")'
    print('Background refresh process started')
    while True:
        try:
            with notify_refresh:
                notify_refresh.wait()
        except IOError:
            # Handle this to avoid traceback on exit
            print('Background update exiting on shutdown')
            return

    for root, dirs, files in os.walk(datadir):
        for topic in dirs:
            if state.get(topic, False):
                _ = exec_livycode(
                    refresh_table_code + call_func.format(topic, datadir,
                                                          tmpdir),
                    session_url, True)
                state[topic] = False
            state['update'] = False
        break


def _main(datadir, tmpdir):

    manager = Manager()
    state = manager.dict({'update': False})
    for root, dirs, files in os.walk(datadir):
        for topic in dirs:
            manager.dict({topic: False})
        break

    notify_refresh = manager.Condition()

    # Need this for jupyter notebook
    import warnings
    warnings.filterwarnings("ignore", message="numpy.dtype size changed")
    warnings.filterwarnings("ignore", message="numpy.ufunc size changed")

    notify_proc = Process(target=inotify_process,
                          args=(state, datadir, notify_refresh))
    notify_proc.daemon = True
    notify_proc.start()

    session_url, response = get_or_create_livysession()
    if not session_url:
        print('Unable to create a Livy session. Aborting')
        sys.exit(1)

    output = exec_livycode(refresh_table_code + initcode.format(datadir,
                                                                tmpdir),
                           session_url, True)
    if output['status'] != 'ok':
        print(output)
    else:
        print('All tables created')

    update_proc = Thread(target=background_refresh_tables,
                         args=(state, datadir, notify_refresh, session_url,
                               tmpdir))
    update_proc.daemon = True
    update_proc.start()

    return session_url


if __name__ == '__main__':
    if len(sys.argv) > 1:
        pqdir = sys.argv[1]
    else:
        pqdir = '/tmp/parquet-out/test/'

    if len(sys.argv) > 2:
        tmpdir = sys.argv[2]
    else:
        tmpdir = '/tmp/suzieq/'

    session_url = _main(pqdir, tmpdir)
    while True:
        # Sleep and send keepalives to keep the Spark session alive
        output = exec_livycode("""spark.conf.get('spark.app.name')""",
                               session_url)
        if output['status'] != 'ok':
            print(output)
        sleep(180)
    
