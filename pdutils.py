from suzieq.utils import get_latest_files, get_display_fields
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pa
import os
from subprocess import check_output


def get_filecnt(path='.'):
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += 1
        elif entry.is_dir():
            total += get_filecnt(entry.path)
    return total


def pd_get_table_df(table: str, start: str, end: str, view: str,
                    sort_fields: list, cfg: dict, schemas: dict,
                    **kwargs) -> pd.DataFrame:
    '''Use Pandas instead of Spark to retrieve the data'''

    MAX_FILECNT_TO_READ_FOLDER = 10000

    sch = schemas.get(table)
    if not sch:
        print('Unknown table {}, no schema found for it'.format(table))
        return ''

    folder = '{}/{}'.format(cfg.get('data-directory'), table)

    fcnt = get_filecnt(folder)

    if fcnt > MAX_FILECNT_TO_READ_FOLDER and view == 'latest':
        # Switch to more efficient method when there are lotsa files
        key_fields = []
        if 'datacenter' in kwargs:
            v = kwargs['datacenter']
            if v:
                if not isinstance(v, list):
                    folder += '/datacenter={}/'.format(v)
                    del kwargs['datacenter']
        files = get_latest_files(folder, start, end)
    else:
        key_fields = [f['name'] for f in sch if f.get('key', None)]

    filters = []
    for k, v in kwargs.items():
        if v and k in key_fields:
            if isinstance(v, list):
                kwdor = []
                for e in v:
                    kwdor.append(tuple(('{}'.format(k), '==', '{}'.format(e))))
                filters.append(kwdor)
            else:
                filters.append(tuple(('{}'.format(k), '==', '{}'.format(v))))

    if 'columns' in kwargs:
        columns = kwargs['columns']
        del kwargs['columns']
    else:
        columns = 'default'

    fields = get_display_fields(table, columns, sch)

    if 'active' not in fields:
        fields.append('active')

    if 'timestamp' not in fields:
        fields.append('timestamp')

    # Create the filter to select only specified columns
    query_str = "active == True "
    for f, v in kwargs.items():
        if not v or f in key_fields:
            continue
        if isinstance(v, str):
            query_str += "and {}=='{}' ".format(f, v)
        else:
            query_str += "and {}=={} ".format(f, v)

    if fcnt > MAX_FILECNT_TO_READ_FOLDER and view == 'latest':
        pdf_list = []
        for file in files:
            # Sadly predicate pushdown doesn't work in this method
            df = pa.ParquetDataset(file).read(columns=fields).to_pandas()
            pth = Path(file).parts
            for elem in pth:
                if '=' in elem:
                    k, v = elem.split('=')
                    df[k] = v
            pdf_list.append(df)

        if pdf_list:
            final_df = pd.concat(pdf_list).query(query_str)

    else:
        if view == 'latest':
            final_df = pa.ParquetDataset(folder, filters=filters or None,
                                         validate_schema=False) \
                         .read(columns=fields) \
                         .to_pandas() \
                         .query(query_str) \
                         .drop_duplicates(subset=key_fields, keep='last')
        else:
            final_df = pa.ParquetDataset(folder, filters=filters or None,
                                         validate_schema=False) \
                         .read(columns=fields) \
                         .to_pandas() \
                         .query(query_str)

    final_df['timestamp'] = pd.to_datetime(pd.to_numeric(final_df['timestamp'],
                                                         downcast='float'),
                                           unit='ms') \
                              .dt.tz_localize('utc') \
                                 .dt.tz_convert('US/Pacific')

    fields.remove('active')

    return(final_df[fields].sort_values(by=sort_fields))

