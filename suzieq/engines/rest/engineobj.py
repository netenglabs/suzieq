from typing import Type, Dict
import urllib
import requests
import urllib3

import pandas as pd

from suzieq.engines.base_engine import SqEngineObj


class SqRestEngine(SqEngineObj):
    '''The basic class implementing the REST engine'''

    def __init__(self, baseobj):
        self.ctxt = baseobj.ctxt
        self.iobj = baseobj

    @property
    def name(self):
        return 'rest'

    def table_name(self):
        '''table name, retrieved from sqobject

        Does it matter that the table name is not a static method as it is
        in pandas?
        '''
        return self.iobj.table

    @classmethod
    def get_plugins(cls,
                    plugin_name: str = None,
                    search_pkg: str = None) -> Dict[str, Type]:
        '''Redefining the base implementation

        We don't need to define specific table plugins for REST engine
        '''
        return {plugin_name: cls}

    def get(self, **kwargs) -> pd.DataFrame:
        '''The catch all get method for all tables'''
        return self._get_response('show', **kwargs)

    def summarize(self, **kwargs):
        return self._get_response('summarize', **kwargs)

    def unique(self, **kwargs):
        return self._get_response('unique', **kwargs)

    def aver(self, **kwargs):
        return self._get_response('assert', **kwargs)

    def top(self, **kwargs):
        return self._get_response('top', **kwargs)

    def find(self, **kwargs):
        return self._get_response('find', **kwargs)

    def lpm(self, **kwargs):
        return self._get_response('lpm', **kwargs)

    def _get_response(self, verb: str, **kwargs) -> pd.DataFrame:
        """The work horse engine implementing the basic REST API query

        Args:
            verb ([str]]): The verb for which we're executing the query
        """

        # Weed out the unspecified parameters
        cmd_params = {'start_time': self.iobj.start_time,
                      'end_time': self.iobj.end_time,
                      'view': kwargs.get('view', self.iobj.view),
                      'namespace': kwargs.get('namespace',
                                              self.iobj.namespace),
                      'hostname': kwargs.get('hostname', self.iobj.hostname),
                      'columns': kwargs.get('columns', self.iobj.columns)}
        kwargs.update(cmd_params)
        # Cannot drop values which are equal to 0 or False
        kwargs = {k: v for k, v in kwargs.items() if v or v in [0, False]}

        query_params = urllib.parse.urlencode(kwargs, doseq=True)

        if not self.ctxt.rest_api_key:
            raise ValueError("No REST API key specified")

        # Suppress warning since most folks will deploy this without
        # verifiable certificates
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        query_params = (
            f'{query_params}&access_token={self.ctxt.rest_api_key}'
        )
        table = self.table_name()
        if table in ['routes', 'macs', 'interfaces']:
            table = table[:-1]
        if table == "tables":
            # Screwup on our side in naming the API
            table = "table"
        url = (
            f'{self.ctxt.rest_transport}://{self.ctxt.rest_server_ip}'
            f':{self.ctxt.rest_server_port}'
            '/api/v2/'
            f'{table}/'
            f'{verb}?'
            f'{query_params}')

        # pylint: disable=missing-timeout
        response = requests.get(url, verify=None)
        if response.status_code != 200:
            if response.text:
                msg = response.json().get("detail", str(response.status_code))
                # Strip out the "ID=" part of the message
                msg = msg.rsplit('id=', 1)[0].strip()
                return pd.DataFrame(
                    {'error': [f'ERROR: {msg}']})

            return pd.DataFrame({'error': [f'{response.status_code}']})

        df = pd.DataFrame(response.json())
        return df
