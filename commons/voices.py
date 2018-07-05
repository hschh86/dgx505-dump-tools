"""
voices.py
"""

# maybe this sort of thing is better done using some sort of database.

import pkgutil
import csv
import collections


Voice = collections.namedtuple("Voice",
                               "number name category msb lsb prog")


def _initialise_dicts():
    _numbers = {}
    _bank_programs = {}
    _names_nonxg = {}
    _names_xg = {}
    # read in data from csv file
    _cdata = pkgutil.get_data(__name__, 'tables/voices.csv').decode('ascii')
    _creader = csv.reader(_cdata.splitlines())
    next(_creader)  # Throw away the header
    for number_s, name, category, msb_s, lsb_s, prog_s in _creader:
        # convert strings to ints
        number, msb, lsb, prog = map(int, (number_s, msb_s, lsb_s, prog_s))
        # construct Voice tuple
        voice = Voice(number, name, category, msb, lsb, prog)
        # assign to dictionaries
        _numbers[number] = voice
        _bank_programs[(msb, lsb, prog)] = voice
        if category.startswith("XG"):
            _names_xg[name] = voice
        else:
            _names_nonxg[name] = voice

    # check we have everything
    assert (len(_numbers)
            == len(_bank_programs)
            == len(_names_nonxg) + len(_names_xg))

    return (_numbers, _bank_programs, _names_nonxg, _names_xg)


_numbers, _bank_programs, _names_nonxg, _names_xg = _initialise_dicts()
_names_nonxg_first = collections.ChainMap(_names_nonxg, _names_xg)
_names_xg_first = collections.ChainMap(_names_xg, _names_nonxg)


def from_name(name, prefer_xg=False):
    """
    Look up a voice by name.
    By default in the case of duplicate names the non-XG voice is preferred
    (use the prefer_xg argument for the opposite behaviour)
    Returns a Voice namedtuple.
    KeyError raised if no voice has that name.
    """
    if prefer_xg:
        return _names_xg_first[name]
    return _names_nonxg_first[name]


def from_number(number):
    """
    Look up a voice by number.
    Returns a Voice namedtuple.
    KeyError raised if no voice has that number.
    """
    return _numbers[number]


def from_bank_program(msb, lsb, prog):
    """
    Look up a voice by bank and program bytes.
    MSB, LSB and Program bytes must be specified.
    Note that this uses the program byte (0-127), which is one less than
    the program number (1-128).
    Returns a Voice namedtuple.
    KeyError raised if no voice has those bytes.
    """
    return _bank_programs[(msb, lsb, prog)]
