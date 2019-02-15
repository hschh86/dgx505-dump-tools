"""
table_util.py

Getting stuff out of the CSV tables
"""

import pkgutil
import csv

def read_csv_table(resource, package=__name__, encoding='utf8', **kwargs):
    """
    Read the data in from the CSV file specified by resource.
    Returns a csv reader object.
    """
    cdata = pkgutil.get_data(package, resource).decode(encoding)
    creader = csv.reader(cdata.splitlines(), **kwargs)
    return creader
