"""
table_util.py

Getting stuff out of the CSV tables
"""

import pkgutil
import csv

from ..util import ListMapping

#Exceptions
class TableUtilError(Exception):
    pass

def read_csv_table(resource, package=__name__, encoding='utf8', **kwargs):
    """
    Read the data in from the CSV file specified by resource.
    Returns a csv reader object.
    """
    cdata = pkgutil.get_data(package, resource).decode(encoding)
    creader = csv.reader(cdata.splitlines(), **kwargs)
    return creader


def read_csv_table_namedtuple(resource, constructor, factories=None,
        header=None, package=__name__, encoding='utf8', **kwargs):
    """
    Read the data in from the CSV file specified by resource,
    and yield it in the form of the provided namedtuple constructor.

    Verifies the first line (headers) is the same as the supplied header.
    If no header provided, then verifies against the namedtuple fields.

    factories is a list of factory functions to convert the strings
    into the correct types for the namedtuple.
    If not provided, no conversion is performed.
    """
    # header default
    if header is None:
        header = constructor._fields

    # verify factories
    if (factories is not None and
            len(constructor._fields) != len(factories)):
        raise TableUtilError(factories)

    reader = read_csv_table(resource, package, encoding, **kwargs)
    # verify the header.
    first = next(reader)
    if first != list(header):
        raise TableUtilError(first)

    # Yield.
    if factories is None:
        yield from (constructor._make(values) for values in reader)
    else:
        for values in reader:
            yield constructor._make(f(x) for f, x in zip(factories, values))


def read_csv_table_namedtuple_listmapping(resource, constructor, factories=None,
        header=None, start=0, package=__name__, encoding='utf8', **kwargs):
    """
    Uses read_csv_table_namedtuple to get the namedtuples, and puts them
    in a ListMapping keyed by the first field.
    """
    nts = read_csv_table_namedtuple(
            resource, constructor, factories, header,
            package, encoding, **kwargs)
    return ListMapping(((t[0], t) for t in nts), start)
