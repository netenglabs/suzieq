from typing import Dict, List
from dataclasses import dataclass, field

from suzieq.shared.utils import SUPPORTED_ENGINES, set_rest_engine


@dataclass
class SqContext:
    '''Context passed between the front-end and back-end'''
    cfg: Dict = field(default_factory=dict)
    schemas: Dict = field(default_factory=dict)

    pager: bool = False
    namespace: str = ''
    hostname: str = ''
    start_time: str = ''
    end_time: str = ''
    exec_time: str = ''
    engine: str = None
    col_width: int = 50
    max_rows: int = 256
    all_columns: bool = False
    debug: bool = False
    sort_fields: List[str] = field(default_factory=list)
    view: str = None
    rest_server_ip: str = '127.0.0.1'
    rest_server_port: int = 8000
    rest_api_key: str = ''
    rest_transport: str = 'https'

    def __post_init__(self):
        # If the engine has not been explicitly set in the context object,
        # get it from the config file
        if not self.engine:
            self.engine = self.cfg.get('ux', {}).get('engine', 'pandas')
            if self.engine == 'rest':
                self.rest_server_ip, \
                 self.rest_server_port, \
                 self.rest_transport, \
                 self.rest_api_key = set_rest_engine(self.cfg)

        if self.engine not in SUPPORTED_ENGINES:
            raise ValueError(f'Engine {self.engine} not supported')
