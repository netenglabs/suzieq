from pandas import DataFrame
from suzieq.sqobjects.basicobj import SqObject


class PathObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='path', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'vrf', 'source', 'dest']

    def summarize(self, namespace=[], hostname=[], source='',
                  dest='', vrf='', query_str='') -> DataFrame():
        """Path summarize, different because of the params

        :param namespace: List{str], can really only be a single namespace
        :param hostname: List[str], ignored for now
        :param source: str, Source IP address,
        :param dest: str, Dest IP address,
        :param vrf: str, VRF within which to run the path
        :param query_str: str, Pandas query string to further refine result
        :returns: Pandas dataframe, summarizing the result
        """
        if self.columns != ["default"]:
            self.summarize_df = DataFrame(
                {'error': ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine.summarize(namespace=namespace, source=source,
                                     dest=dest, vrf=vrf, query_str=query_str)
