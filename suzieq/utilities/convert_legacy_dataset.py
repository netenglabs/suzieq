#!/usr/bin/env python

import sys
import pyarrow.parquet as pq
import pyarrow as pa
from suzieq.utils import Schema, SchemaForTable
import logging
import argparse
import pandas as pd
from pathlib import Path


def convert_dir(input_dir: str, output_dir: str, svcschema: SchemaForTable):
    """Convert the data into a single file and write it out"""

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

    df = pd.read_parquet(input_dir, use_legacy_dataset=True)
    sqschema = svcschema.get_raw_schema()
    arrow_schema = svc_schema.get_arrow_schema()

    for column in filter(lambda x: x['name'] not in df.columns, sqschema):
        df[column['name']] = column.get('default', defaults[column['type']])

    # convert all dtypes to whatever is desired
    for column in df.columns:
        if column in arrow_schema:
            df[column] = df[column].astype(arrow_schema.field(column)
                                           .type.to_pandas_dtype())

    # If there's the original ifname saved up, then eliminate this unnecessary
    # field as this model is no longer necessary

    if 'origIfname' in df.columns:
        if 'ifname' in df.columns:
            df = df.drop(columns=['ifname']) \
                   .rename(columns={'origIfname': 'ifname'})
        elif 'oif' in df.columns:
            df = df.drop(columns=['oif']) \
                   .rename(columns={'origIfname': 'oif'})

    table = pa.Table.from_pandas(df, schema=arrow_schema,
                                 preserve_index=False)
    partition_cols = svcschema.get_partition_columns()

    if 'norifcnReason' in df.columns:
        df.rename({'notifcnReason': 'notificnReason'}, inplace=True)

    pq.write_to_dataset(
        table,
        root_path=output_dir,
        partition_cols=partition_cols,
        version="2.0",
        compression='ZSTD',
        row_group_size=100000,
    )

    logger.info(f'Wrote converted {input_dir}')


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Usage: convert_parquet <input dir> <output_dir> <schema_dir>')
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = sys.argv[2]
    schemas = Schema(sys.argv[3])
    service = input_dir.parts[-1]
    svc_schema = SchemaForTable(service, schema=schemas)

    logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
    logger = logging.getLogger('sq-converter')
    convert_dir(input_dir, output_dir, svc_schema)
