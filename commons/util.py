"""
util.py

Utilities that don't require mido

(Just contains eprint, that prints to stderr.)
"""

import sys
def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)
