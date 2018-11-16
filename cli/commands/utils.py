import re

code_tmpl = '''
import sys
sys.path.append("/home/ddutt/work/suzieq/")
from livylib import get_latest_files

files = dict()
for k in {1}:
    v = get_latest_files("{0}" + "/" + k, start="{3}", end="{4}")
    files[k] = v

for k, v in files.items():
    spark.read.option("basePath", "{0}").load(v).createOrReplaceTempView(k)

x={2}
for k in {1}:
  spark.catalog.dropTempView(k)
x
'''

counter_code_tmpl = '''
import pyspark.sql.functions as F
from pyspark.sql.window import Window

for k in {1}:
    spark.read.option("basePath", "{0}").load("{0}/" + k).createOrReplaceTempView(k)

cntrdf={2}

col_name = "{3}"
cntrdf = cntrdf \
             .withColumn('prevTime',
                         F.lag(cntrdf.timestamp).over(Window.partitionBy()
                                                      .orderBy('timestamp')))
cntrdf = cntrdf \
             .withColumn('prevBytes',
                         F.lag(col_name).over(Window.partitionBy()
                                              .orderBy('timestamp')))

cntrdf = cntrdf \
             .withColumn("rate",
                         F.when(F.isnull(F.col(col_name) - cntrdf.prevBytes), 0)
                         .otherwise((F.col(col_name) - cntrdf.prevBytes)*8 /
                                    (cntrdf.timestamp.astype('double')-cntrdf.prevTime.astype('double')))) \
             .drop('prevTime', 'prevBytes')

for k in {1}:
  spark.catalog.dropTempView(k)

cntrdf.toJSON().collect()
'''


def get_spark_code(qstr, cfg, schemas, start=None, end=None):
    '''Get the Table creation and destruction code for query string'''

    # SQL syntax has keywords separated by space, multiple values for a keyword
    # separated by comma.
    qparts = re.split(r'(?<!,)\s+', qstr)
    tables = []
    counter = None

    # Check if any of the select columns have a rate field
    if qparts[0] == 'select':
        fields = re.split(r',\s*', qparts[1])
        newfields = []
        for field in fields:
            if 'rate(' in field:
                mstr = re.match(r'rate\s*\(\s*(\s*\w+\s*)\s*\)', field)
                if mstr:
                    counter = mstr[1]
                    newfields.append(counter)
            else:
                newfields.append(field)

        qparts[1] = ', '.join(newfields)

    if counter:
        # We need to apply time window to sql
        windex = [i for i, x in enumerate(qparts) if x.lower() == "where"]
        timestr = ("timestamp(timestamp/1000) > timestamp('{}') and "
                   "timestamp(timestamp/1000) < timestamp('{}') and ".format(start, end))
        qparts.insert(windex[0]+1, timestr)

    qstr = ' '.join(qparts)

    indices = [i for i, x in enumerate(qparts) if x.lower() == "from"]
    indices += [i for i, x in enumerate(qparts) if x.lower() == "join"]

    for index in indices:
        words = re.split(r',\s*', qparts[index+1])
        for table in words:
            if table in schemas:
                tables.append(table)

    if counter:
        sstr = 'spark.sql("{0}")'.format(qstr)
        cprint(sstr)
        code = counter_code_tmpl.format(cfg['data-directory'], tables,
                                        sstr, counter)
    else:
        sstr = 'spark.sql("{0}").toJSON().collect()'.format(qstr)
        code = code_tmpl.format(cfg['data-directory'], tables, sstr,
                                start, end)

    return code

