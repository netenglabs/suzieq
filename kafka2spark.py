#!/usr/bin/env python

import os
packages = "org.apache.spark:spark-sql-kafka-0-10_2.11:2.3.0"

os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages {0} pyspark-shell".format(packages)
)

import sys
sys.path.append("./schema")

import findspark
findspark.init(spark_home='/opt/spark')
import pyspark


from pyspark.sql import SparkSession
from pyspark.sql.functions import explode
from pyspark.sql.functions import split
from pyspark.sql.functions import col
from pyspark.sql.functions import from_json
import schemas
from pykafka import KafkaClient
from time import sleep
from shutil import rmtree

def start_new_ssquery(sc, topic, schema):
    '''Start a new streaming query for the given topic and schema'''
    df = sc \
         .readStream \
         .format("kafka")  \
         .option("kafka.bootstrap.servers", "localhost:9092") \
         .option("subscribe", topic) \
         .option("startingOffsets", "earliest") \
         .load()


    parsed_df = df \
                .select(col("value").cast("string").alias('json')) \
                .select(from_json('json', schema).alias("data")) \
                .select("data.*") \
                .where((col('active') != "0") | (col('deleted') != "0"))

    if topic == 'route':
        parsed_df = parsed_df.where((col('prefix').startswith('fe80::')) == False)

    out = parsed_df \
          .writeStream \
          .format("parquet") \
          .option("path", "parquet-out/{}".format(topic)) \
          .trigger(processingTime="10 seconds") \
          .option("checkpointLocation", "checkpoints/{}".format(topic)) \
          .option("truncate", False) \
          .queryName(topic) \
          .start()

    return out

if __name__ == "__main__":
    sparkSession = SparkSession \
                   .builder     \
                   .appName("Kfk2Spark") \
                   .getOrCreate()
    query_topics = {}
    
    while True:
        kc = KafkaClient()

        # Reload schemas library
        reload(schemas)

        for topic in kc.topics:
            if topic not in query_topics and topic in schemas.ss_schemas:
                print("Adding topic {} to streaming list".format(topic))
                query_topics[topic] = {}
                query_topics[topic]['query'] = start_new_ssquery(
                    sparkSession, topic, schemas.ss_schemas[topic])
                query_topics[topic]['schemas'] = schemas.ss_schemas[topic]
            elif (topic in query_topics and
                  query_topics[topic]['schemas'] != schemas.ss_schemas[topic]):
                    print("Reparsing topic {} due to changed schema".format(topic))
                    query_topics[topic]['query'].stop()

                    # Move the directories
                    try:
                        rmtree("parquet-out/{}-old".format(topic))
                        rmtree("checkpoints/{}-old".format(topic))
                    except Exception:
                        pass

                    os.rename("parquet-out/{}".format(topic),
                              "parquet-out/{}-old".format(topic))
                        
                    os.rename("checkpoints/{}".format(topic),
                              "checkpoints/{}-old".format(topic))

                    query_topics[topic]['query'] = start_new_ssquery(
                        sparkSession, topic, schemas.ss_schemas[topic])
                    query_topics[topic]['schemas'] = schemas.ss_schemas[topic]
                

        sleep(20)

