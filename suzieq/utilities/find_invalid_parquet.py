""" searches the provided parquet-out directory to find any invalid files 
    it just finds all the parquet files and tries to load them as valid files
    if there is an exception, then we know it's a bad file
"""

# TODO
#  figure out how to break the files into multiple processes, otherwise
#  it gets stuck behind a single core

from suzieq.utils import get_latest_files
import argparse
import os
import pyarrow.parquet as pa

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--parquet_dir', type=str, required=True,
                        help="parquet directory")
    userargs = parser.parse_args()

    # this doesn't work, it's broken and doesn't return all the files
    #files = get_latest_files(f"{userargs.parquet_dir}/{table}", view='all')

    all_files = []
    broken_files = []
    for root, dirs, files in os.walk(f"{userargs.parquet_dir}"):
        if not '_archived' in root and not '_broken' in root and not '.sq-coalescer.pid' in files:
            all_files.extend(list(map(lambda x: f"{root}/{x}", files)))
    print(f"{len(all_files)} files")

    
    for file in all_files:
        try:
            parquet_file = pa.ParquetFile(file)
        except pa.lib.ArrowInvalid as e:
            broken_files.append(file)

    print(f"Broken files: {broken_files}")
