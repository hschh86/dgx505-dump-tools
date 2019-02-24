"""
styles.py
"""

import collections

from . import table_util
from .. import util

class Style(collections.namedtuple('Style', 'number name category')):
    __slots__ = ()

    def __str__(self):
        return "{:03d} {}".format(self.number, self.name)

class _StyleLookup(object):
    @util.lazy_property
    def numbers(self):
        return table_util.read_csv_table_namedtuple_listmapping(
            'tables/styles.csv', Style, [int, str, str], start=1)
    
    @util.lazy_property
    def names(self):
        return {s.name: s for s in self.numbers.values()}

_LOOKUP = _StyleLookup()

def from_number(number):
    """
    Look up a style by number.
    Returns a Style namedtuple.
    KeyError raised if no style has that number.
    """
    return _LOOKUP.numbers[number]

def from_name(name, prefer_xg=False):
    """
    Look up a style by name.
    KeyError raised if no style has that name.
    """
    return _LOOKUP.names[name]
