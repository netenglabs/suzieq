#!/usr/bin/env python

import json, textwrap, requests
from time import sleep

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

    data = {'code': textwrap.dedent('''{code}'''.format(code=code))}
    statements_url = session_url + '/statements'

    try:
        r = requests.post(statements_url, data=json.dumps(data), headers=headers)
        
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
    
    return r.json()['output']
    

def get_livysession(server_url='http://localhost:8998'):
    headers = {'Content-Type': 'application/json'}
    
    s_response = requests.get(server_url + '/sessions', headers=headers)
    if s_response.status_code == requests.codes.ok:
        s_json = s_response.json()
        for session in s_json['sessions']:
            session_url = server_url + '/sessions/' + str(session['id'])
            try:
                resp = exec_livycode("""spark.conf.get('spark.app.name')""",
                                     session_url)
                # TODO check valid response code
                appname = resp['data']['text/plain']
                if appname == u"u'suzieq'":
                    return session_url
            except requests.HTTPError:
                print('Exception raised by Livy, aborting')
                return None
    return None


def get_or_create_livysession(server_url='http://localhost:8998'):
    ''' Create a new pyspark session with Livy REST server, if not existing

        It checks if an existing session with app name suzieq exists and if
        it does, it returns that session URL, else creates a new session and
        returns that info

        Inputs: Livy server URL
        Returns: session ID to use in job submissions, response
    '''

    headers = {'Content-Type': 'application/json'}

    session_url = get_livysession(server_url)
    if session_url:
        return session_url, None
    
    data = {'kind': 'pyspark', 'heartbeatTimeoutInSecond': 3600,
            'conf': {'spark.app.name': 'suzieq'}, 'executorCores': 2}
    r = requests.post(server_url + '/sessions', data=json.dumps(data), headers=headers)
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

