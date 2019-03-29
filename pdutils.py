from suzieq.utils import get_latest_files, get_display_fields
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pa


def pd_get_table_df(table:str, start: str, end: str, view: str,
                    sort_fields: list, cfg: dict, schemas: dict,
                    **kwargs) -> pd.DataFrame:
    '''Use Pandas instead of Spark to retrieve the data'''

    sch = schemas.get(table)
    if not sch:
        print('Unknown table {}, no schema found for it'.format(table))
        return ''

    folder = '{}/{}'.format(cfg.get('data-directory'), table)
    files = get_latest_files(folder, start, end)
    pdf_list = []
    final_df = None

    if 'columns' in kwargs:
        columns = kwargs['columns']
        del kwargs['columns']
    else:
        columns = 'default'

    fields = get_display_fields(table, columns, sch)
    if 'timestamp' not in fields:
        fields.append('timestamp')

    if 'datacenter' not in fields:
        fields.insert(0, 'datacenter')

    for file in files:
        df = pa.ParquetDataset(file,
                               filters=[('active', '==', True)]) \
               .read(columns=fields).to_pandas()
        pth = Path(file).parts
        for elem in pth:
            if '=' in elem:
                k, v = elem.split('=')
                df[k] = v
        pdf_list.append(df)

    if pdf_list:
        final_df = pd.concat(pdf_list)

    return(final_df[fields].sort_values(by=sort_fields))
