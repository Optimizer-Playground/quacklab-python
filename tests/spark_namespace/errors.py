from . import USE_ACTUAL_SPARK

if USE_ACTUAL_SPARK:
    from pyspark.errors import *
else:
    from quacklab.experimental.spark.errors import *
