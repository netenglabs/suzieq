#!/usr/bin/env python

import sys
import typing
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path, PosixPath
from suzieq.utils import Schema, SchemaForTable
import concurrent.futures
import logging


def convert_file(file: PosixPath, output_dir: str, schema: SchemaForTable,
                 defaults: typing.List,
                 arrow_schema: pa.lib.Schema,
                 new_partition_columns=['sqvers', 'namespace', 'hostname']):
    """Read the dataset from file and convert it. No compaction."""

    logger.info(f'Reading {file}')
    df = pq.ParquetDataset(file, use_legacy_dataset=True,
                           validate_schema=False, partitioning='hive') \
        .read() \
        .to_pandas()

    part_data = [x.split('=') for x in file.parts if '=' in x]
    for elem in part_data:
        df[elem[0]] = elem[1]

    for column in filter(lambda x: x['name'] not in df.columns, schema):
        df[column['name']] = column.get('default', defaults[column['type']])

    # If there's the original ifname saved up, then eliminate this unnecessary
    # field as this model is no longer necessary

    if 'origIfname' in df.columns:
        if 'ifname' in df.columns:
            df = df.drop(columns=['ifname']) \
                   .rename(columns={'origIfname': 'ifname'})
        elif 'oif' in df.columns:
            df = df.drop(columns=['oif']) \
                   .rename(columns={'origIfname': 'oif'})

    # convert all dtypes to whatever is desired
    for column in df.columns:
        df[column] = df[column].astype(arrow_schema.field(column)
                                       .type.to_pandas_dtype())

    table = pa.Table.from_pandas(df, schema=arrow_schema, preserve_index=False)

    pq.write_to_dataset(
        table,
        root_path=output_dir,
        partition_cols=new_partition_columns,
        version="2.0",
        compression='ZSTD',
        row_group_size=100000,
    )
    logger.info(f'Wrote converted {file}')

    return file


def convert_dir(input_dir: str, output_dir: str, sqschema: typing.List,
                arrow_schema: pa.lib.Schema):
    """Spawn off threads to convert directory"""

    files = Path(input_dir).glob('**/*.parquet')

    defaults = {
        pa.string(): "",
        pa.int32(): 0,
        pa.int64(): 0,
        pa.float32(): 0.0,
        pa.float64(): 0.0,
        pa.date64(): 0.0,
        pa.bool_(): False,
        pa.list_(pa.string()): ['-'],
        pa.list_(pa.int64()): [],
    }

    with concurrent.futures.ProcessPoolExecutor(max_workers=None) as thread:
        threads = {thread.submit(convert_file, item,
                                 output_dir, sqschema, defaults, arrow_schema)
                   for item in files}
        for future in concurrent.futures.as_completed(threads):
            try:
                _ = future.result()
            except Exception:
                logger.exception(f'Exception occcurred with {future}')


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Usage: convert_parquet <input dir> <output_dir> <schema_dir>')
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = sys.argv[2]
    schemas = Schema(sys.argv[3])
    service = input_dir.parts[-1]
    svc_schema = SchemaForTable(service, schema=schemas)
    arrow_schema = svc_schema.get_arrow_schema()
    sqschema = svc_schema.get_raw_schema()

    logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
    logger = logging.getLogger('sq-converter')
    convert_dir(input_dir, output_dir, sqschema, arrow_schema)
