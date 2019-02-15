"""
chords.py

Classes and utilities for handling and representing the chord change information.
"""

import collections

from . import table_util
from .. import util

ChordType = collections.namedtuple('ChordType', 'code name abbr abbr_format disp_format')

class _ChordLookup(object):

    @util.lazy_property
    def codes(self):
        cmap = util.ListMapping()
        creader = table_util.read_csv_table('tables/chords.csv')

        # header check
        headers = next(creader)
        assert headers == list(ChordType._fields)

        for code_hex, *rest in creader:
            # Convert the hex string to a number
            code = int(code_hex, 16)
            cmap[code] = ChordType(code, *rest)
        return cmap
    
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


