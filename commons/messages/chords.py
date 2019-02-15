"""
chords.py

Classes and utilities for handling and representing the chord change information.
"""

import collections
from functools import partial

from . import table_util
from .. import util

ChordType = collections.namedtuple('ChordType', 'code name abbr abbr_format disp_format')

class _ChordLookup(object):

    @util.lazy_property
    def codes(self):
        return table_util.read_csv_table_namedtuple_listmapping(
            'tables/chords.csv', ChordType, [partial(int, base=16), str, str, str, str])

    @util.lazy_property
    def names(self):
        return {c.name: c for c in self.codes.values()}

    @util.lazy_property
    def abbrs(self):
        return {c.abbr: c for c in self.codes.values()}

CHORDS = _ChordLookup()

class Chord(collections.namedtuple('Chord', 'root type bass')):
    __slots__ = ()

    # A Chord has three parts.
    def __new__(cls, root, type, bass=None):
        return super().__new__(cls, root, type, bass)


