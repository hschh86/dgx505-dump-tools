"""
voices.py
"""

import pkgutil
import csv
import collections


_Voice = collections.namedtuple("Voice",
                                "number name category msb lsb prog")

NUMBERS = {}
BANK_PROGRAMS = {}
NAMES_NONXG = {}
NAMES_XG = {}
# read in data from csv file
_cdata = pkgutil.get_data(__name__, 'tables/voices.csv').decode('ascii')
_creader = csv.reader(_cdata.splitlines())
next(_creader)  # Throw away the header
for number_s, name, category, msb_s, lsb_s, prog_s in _creader:
    # convert strings to ints
    number, msb, lsb, prog = map(int, (number_s, msb_s, lsb_s, prog_s))
    # construct Voice tuple
    voice = _Voice(number, name, category, msb, lsb, prog)
    # assign to dictionaries
    NUMBERS[number] = voice
    BANK_PROGRAMS[(msb, lsb, prog)] = voice
    if category.startswith("XG"):
        NAMES_XG[name] = voice
    else:
        NAMES_NONXG[name] = voice
del _creader, number_s, name, category, msb_s, lsb_s, prog_s
# because why not?

# Check that we have everything
assert len(NUMBERS) == len(BANK_PROGRAMS) == len(NAMES_NONXG) + len(NAMES_XG)


def from_name(name, prefer_xg=False):
    """
    Look up a voice by name.
    By default in the case of duplicate names the non-XG voice is preferred
    (use the prefer_xg argument for the opposite behaviour)
    Returns a Voice namedtuple.
    KeyError raised if no voice has that name.
    """
    if not prefer_xg:
        try:
            return NAMES_NONXG[name]
        except KeyError:
            pass  # fall through
    return NAMES_XG[name]


def from_number(number):
    """
    Look up a voice by number.
    Returns a Voice namedtuple.
    KeyError raised if no voice has that number.
    """
    return NUMBERS[number]


def from_bank_program(msb, lsb, prog):
    """
    Look up a voice by bank and program bytes.
    MSB, LSB and Program bytes must be specified.
    Note that this uses the program byte (0-127), which is one less than
    the program number (1-128).
    Returns a Voice namedtuple.
    KeyError raised if no voice has those bytes.
    """
    return BANK_PROGRAMS[(msb, lsb, prog)]
