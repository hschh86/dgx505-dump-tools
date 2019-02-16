"""
exclusives.py
"""

# another attempt at parsing the SysEx messages
# --- but not wrapping them this time.


# We need to support various SysEx message types:

# 7E 7F 09 01 : GM ON (USE)
# 7F 7F 04 01 ll mm F7:  MIDI Master Volume (USE)

# 43 1n 27 30 00 xm xl xx: MIDI Master Tuning (Yamaha)

# XG Parameter Set
# 43 1n 4C aa aa aa dd.. :

# 43 1n 4C 02 01 00 mm ll: Reverb Type (XG)
# 43 1n 4C 02 01 20 mm ll: Chorus Type (XG)
# 43 1n 4C 00 00 7E 00 : XG ON (XG)
# 43 1n 4C 00 00 7F 00 : All Reset (XG)


# We may also want to support some of the messages
# found in the supplied MID.

# 43 7E 02 rr tt rr tt : Chord Change (Yamaha)
# 43 73 01 50 12 00 xx xx : ????


# The following seqspec metaevents:

# 43 76 1A 01 ss : Section change
# 43 76 1A 02 vv : Volume
# 43 76 1A 03 rr tt rr tt : Chord
# 43 76 1A 04 ss ss : Style Number

# Found in the supplied MID:

# Refer to the Yamaha XF format specification.

# XF Version ID
# 43 7B 00 58 46 30 32 00 1B :
#         " X  F  0  2"s1 s0
# where s1 s0 are flags: 00000000 000kl0si

# XF Guide Track Flag
# 43 7B 0C 01 02
# 43 7B 0C rr ll


import re
import collections

from .wrappers import MessageType, SysEx, SeqSpec
from .. import util

class DataMatcher(object):
    def __init__(self):
        self._matchers = collections.OrderedDict()

    def register(self, pattern):
        """
        Register a pattern
        """
        # Decorators, probably not the best choice (TM)
        regex = re.compile(pattern, flags=re.S)

        def r_decorator(action):
            # We need to decorate... but we don't actually
            # need to return an actual decorated function do we?
            self._matchers[regex] = action
            return action  # maybe unncessary?
        
        return r_decorator

    def match(self, data):
        """
        Match the data against the matchers
        """
        for regex, action in self._matchers.items():
            match = regex.fullmatch(data)
            if match is not None:
                # Matched. Try to run the action with the match
                return action(match)
                # Should we just hand over or should we wrap??
        return None
    
    def matchdict(self, data, **kwargs):
        mdict = self.match(data)
        if mdict is not None:
            mdict.update(kwargs)
            return mdict
        

SysExMatcher = DataMatcher()

# Let's start with GM_ON. 7E 7F 09 01
@SysExMatcher.register(rb'\x7E\x7F\x09\x01')
def _gm_on(match):
    return {'type': SysEx.GM_ON}

# 7F 7F 04 01 ll mm F7:  MIDI Master Volume (USE)
@SysExMatcher.register(rb'\x7F\x7F\x04\x01(..)')
def _master_vol(match):
    ll, mm = match.group(1)
    return {'type': SysEx.MASTER_VOL, 'll': ll, 'mm': mm}

# 43 1n .. : Yamaha Device Things
@SysExMatcher.register(rb'\x43([\x10-\x1F])(.*)')
def _yamaha_dev(match):
    (dev,), rest = match.groups()
    # Need to do more sub matching!
    return YamahaDevMatcher.matchdict(rest, n=dev & 0xF)


YamahaDevMatcher = DataMatcher()

# 43 1n 4C aa aa aa dd..
@YamahaDevMatcher.register(rb'\x4C(.*)')
def _xg_parameter(match):
    rest = match.group(1)
    return XGParameterMatcher.match(rest)

# 43 1n 27 30 00 00 mm ll cc 
@YamahaDevMatcher.register(rb'\x27\x30\x00\x00(...)')
def _master_tuning(match):
    mm, ll, cc = match.group(1)
    return {'type': SysEx.MASTER_TUNE, 'mm': mm, 'll': ll, 'cc': cc}

XGParameterMatcher = DataMatcher()

# .. 02 01 00 mm ll, .. 02 01 20 mm ll
_EFFECT_S = {0x00: SysEx.REVERB_TYPE, 0x20: SysEx.CHORUS_TYPE}
@XGParameterMatcher.register(rb'\x02\x01([\x00\x20]..)')
def _reverb_type(match):
    t, mm, ll = match.group(1)
    return {'type': _EFFECT_S[t], 'mm': mm, 'll': ll}

# .. 00 00 7E 00, .. 00 00 7F 00
_RESET_S = {0x7E: SysEx.XG_ON, 0x7F: SysEx.XG_RESET}
@XGParameterMatcher.register(rb'\x00\x00([\x7E\x7F])\x00')
def _xg_on(match):
    t, = match.group(1)
    return {'type': _RESET_S[t]}

# 43 7E 02 cr ct bn bt
@SysExMatcher.register(rb'\x43\x7E\x02(....)')
def _chord_change(match):
    cr, ct, bn, bt = match.group(1)
    return {'type': SysEx.CHORD, 'cr': cr, 'ct': ct, 'bn': bn, 'bt': bt}


def match_sysex(message):
    return SysExMatcher.match(bytes(message.data))


# Sequencer Specific
SeqSpecMatcher = DataMatcher()

# 43 76 1A tt
@SeqSpecMatcher.register(rb'\x43\x76\x1A(.*)')
def _user_song_seqspec(match):
    rest = match.group(1)
    return UserSongMatcher.match(rest)

UserSongMatcher = DataMatcher()

# .. 01 ss
@UserSongMatcher.register(rb'\x01(.)')
def _section_change(match):
    ss, = match.group(1)
    return {'type': SeqSpec.SECTION, 'ss': ss}

# .. 02 vv
@UserSongMatcher.register(rb'\x02(.)')
def _style_vol(match):
    vv, = match.group(1)
    return {'type': SeqSpec.STYLE_VOL, 'vv': vv}

# .. 03 cr ct bn bt
@UserSongMatcher.register(rb'\x03(....)')
def _seqspec_chord(match):
    cr, ct, bn, bt = match.group(1)
    return {'type': SeqSpec.CHORD, 'cr': cr, 'ct': ct, 'bn': bn, 'bt': bt}

# .. 04 ss ss
@UserSongMatcher.register(rb'\x04(..)')
def _style(match):
    ss = tuple(match.group(1))
    return {'type': SeqSpec.STYLE, 'ss': ss}

# 43 7B 00 58 46 30 32 00 xx
@SeqSpecMatcher.register(rb'\x43\x7B\x00(XF0[12])\x00([\x00-\x1F])')
def _xf_version(match):
    version, (flags,) = match.group(1)
    k, l, x, s, i = util.boolean_bitarray_tuple(flags, 5)
    if not x:
        return {'type': SeqSpec.XF_VERSION,
            'version': version,
            'k': k, 'l': l, 's': s, 'i': i}

# 43 7B 0C rr ll
@SeqSpecMatcher.register(rb'\x43\x7B\x0C(..)')
def _xf_guide(match):
    rr, ll = match.group(1)
    return {'type': SeqSpec.GUIDE_TRACK, 'rr': rr, 'll': ll}

