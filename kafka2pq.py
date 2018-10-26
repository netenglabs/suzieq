#!/usr/bin/env python

import sys
import argparse
from time import sleep
import yaml
import json
from collections import defaultdict
from pathlib import Path
import logging

import os
packages = "org.apache.spark:spark-sql-kafka-0-10_2.11:2.3.1"

os.environ["PYSPARK_SUBMIT_ARGS"] = (
   "--packages {0} pyspark-shell".format(packages)
)

import findspark
findspark.init(spark_home='/opt/spark')
import pyspark

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, split, from_json
from pyspark.sql.types import StructType, StringType, LongType, IntegerType, \
    BooleanType, ArrayType, DoubleType, FloatType


from confluent_kafka import Consumer


def avro_to_spark_schema(avro_sch):

    spark_sch = 'StructType()'

    map_type = {'string': 'StringType()',
                'long': 'LongType()',
                'int': 'IntegerType()',
                'double': 'DoubleType()',
                'float': 'FloatType()',
                'timestamp': 'LongType()',
                'timedelta64[s]': 'DoubleType()',
                'boolean': 'BooleanType()',
                'array.string': 'ArrayType(StringType())',
                'array.long': 'ArrayType(LongType())',
                }

    key_fields = []
    tmp_fields = []
    rectype = avro_sch.get('recordType', 'state')

    for fld in avro_sch.get('fields', None):
        if type(fld['type']) is dict:
            if fld['type']['type'] == 'array':
                avtype = 'array.{}'.format(fld['type']['items']['type'])
            else:
                # We don't support map yet
                raise AttributeError
        else:
            avtype = fld['type']

        spark_sch += '.add("{}", {})'.format(fld['name'], map_type[avtype])
        if fld.get('key', None) is not None:
            tmp_fields.append([fld['key'], fld['name']])

    if rectype == 'counters':
        key_fields = ['datacenter', 'hostname']
    else:
        key_fields = [x[1] for x in sorted(tmp_fields, key=lambda x: x[0])]
        key_fields.append('timestamp')

    return({'schema': eval(spark_sch), 'partitionBy': key_fields})


def get_schemas(schema_dir):
    '''Get the schemas defined in Spark format'''

    schemas = {}
    p = Path(schema_dir).glob('*.avsc')
    for file in p:
        with open(file, 'r') as f:
            avsc = json.loads(f.read())

        schemas.update({avsc['name']: avro_to_spark_schema(avsc)})

    return schemas


def create_host_to_dc_map(hosts_file, logger):
    '''Returns the mapping of hostname to datacenter name'''

    nodes = {}

    if not os.path.isfile(hosts_file):
        logger.error('hosts config must be a file: {}', hosts_file)
        return nodes

    if not os.access(hosts_file, os.R_OK):
        logger.error('hosts config file is not readable: {}', hosts_file)
        return nodes

    with open(hosts_file, 'r') as f:
        try:
            hostsconf = yaml.load(f.read())
        except Exception as e:
            logging.error('Invalid hosts config file:{}', e)
            print('Invalid hosts config file:{}', e)
            sys.exit(1)

    for datacenter in hostsconf:
        if 'datacenter' not in datacenter:
            logging.warning('No datacenter specified, assuming "default"')
            dcname = "default"
        else:
            dcname = datacenter['datacenter']

        for host in datacenter.get('hosts', []):
            nodes[host] = dcname

    return nodes


def start_new_ssquery(topic, kafka_servers, pqdir, schema):
    '''Start a new streaming query for the given topic and schema'''
    df = spark \
        .readStream \
        .format("kafka")  \
        .option("kafka.bootstrap.servers", kafka_servers) \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .load()

    parsed_df = df.select(col("value").cast("string").alias('json')) \
                  .select(from_json('json', schema['schema']).alias("data")) \
                  .select("data.*")

# if topic == 'route':
#    parsed_df = parsed_df.where((col('prefix').startswith('fe80::')) == False)

    out = parsed_df \
        .writeStream \
        .format("parquet") \
        .option("path", "{}/{}".format(pqdir, topic)) \
        .partitionBy(schema['partitionBy']) \
        .trigger(processingTime="5 seconds") \
        .option("checkpointLocation", "{}/_checkpoints/{}".format(pqdir,
                                                                  topic)) \
        .option("truncate", False) \
        .queryName(topic) \
        .start()

    return out


if __name__ == "__main__":
    
    homedir = str(Path.home())

    parser = argparse.ArgumentParser()
    # parser.add_argument('-H', '--hosts-file', type=str,
    #                    default='{}/{}'.format(homedir, 'suzieq-hosts.yml'),
    #                    help='File with URL of mapping hosts to datacenter')
    parser.add_argument('-k', '--kafka-servers', default='localhost:9092',
                        type=str,
                        help='Comma separated list of kafka servers/port')
    parser.add_argument('-l', '--log', type=str, default='WARNING',
                        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help='Logging message level, default is WARNING')
    parser.add_argument('-O', '--output-dir', type=str,
                        default='/tmp/suzieq/',
                        help='Directory to store parquet output in')
    parser.add_argument('-s', '--service-only', type=str,
                        help='Only run this comma separated list of services')
    parser.add_argument('-T', '--schema-dir', type=str, required=True,
                        help='Directory with schema definition for services')

    userargs = parser.parse_args()
    logging.basicConfig(filename='/tmp/suzieq.log',
                        level=getattr(logging, userargs.log.upper()),
                        format='%(asctime)s - %(name)s - %(levelname)s'
                        '- %(message)s')

    logger = logging.getLogger('suzieq')

    # node_dc_map = create_host_to_dc_map(userargs.hosts_file, logger)
    schemas = get_schemas(userargs.schema_dir)

    spark = SparkSession \
        .builder     \
        .appName("suzieq-pq") \
        .getOrCreate()

    queried_topics = []

    while True:
        kc = Consumer({'bootstrap.servers': userargs.kafka_servers})

        topics = kc.list_topics()

        for topic in topics.topics:
            if userargs.service_only and topic != userargs.service_only:
                queried_topics.append(topic)

            if topic not in queried_topics and topic in schemas:
                start_new_ssquery(topic, userargs.kafka_servers,
                                  userargs.output_dir + '/parquet-out/',
                                  schemas[topic])
                queried_topics.append(topic)

        sleep(3600)

