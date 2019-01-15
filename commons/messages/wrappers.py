"""
wrappers.py

Wrappers for mido messages.

The intent of these is to have a more friendly way of
displaying and working with control and sysex messages.
"""
# I'm not sure if that goal is achieved. May have gone overboard with classes

# Should these be wrappers, subclasses, or entirely different???
import re

from ..enums import ReverbType, ChorusType

class WrappedMessage(object):
    # These are wrapped mido messages.
    # Like normal messages, but with some extra metadata.
    type = "message"

    def __init__(self, message):
        """
        Wrap a mido message.
        """
        # I suppose we could use FrozenMessages here, 
        # but we are all responsible adults, right?
        self.message = message
    
    def __str__(self):
        return str(self.message)

    def __repr__(self):
        return "<{} {!r}>".format(self.type, self.message)


class WrappedSysEx(WrappedMessage):
    type = "sysex"
    
    def __init__(self, message, match=None):
        super().__init__(self, message)
        self._process(match)
    
    def _process(self, match):
        pass


class WrappedGMSystemOn(WrappedSysEx):
    # GM System ON, F0 7E 7F 09 01 F7
    type = "gm_on"
    REGEX = re.compile(rb'\x7E\x7F\x09\x01\xF7', re.S)


class WrappedMIDIMasterVolume(WrappedSysEx):
    # MIDI Master Volume, F0 7F 7F 04 01 ** mm F7
    type = "master_vol"
    REGEX = re.compile(rb'\x7F\x7F\x04\x01.(.)', re.S)
    def _process(self, match):
        self.value, = match.group(1)


class WrappedMIDIMasterTuning(WrappedSysEx):
    # MIDI Master Tuning, F0 43 1* 27 30 00 00 *m *l ** F7
    type = "master_tuning"
    REGEX = re.compile(rb'\x43[\x10-\x1F]\x27\x30\x00\x00(..).', re.S)
    def _process(self, match):
        self.msb, self.lsb = match.group(1)
        # we take the least significant nybble of each.
        ml = ((self.msb & 0xF) << 4) | (self.lsb & 0xF)
        # subtract 0x80 and clamp to range -100 +100
        self.value = max(-100, min(ml-0x80, +100))


class WrappedReverbChorus(WrappedSysEx):
    # Reverb Type, F0 43 1n 4C 02 01 00 mm ll F7
    # Chorus Type, F0 43 1n 4C 02 01 20 mm ll F7
    TABLE = (None, {})
   
    def _process(self, match):
        self.msb, self.lsb = match.group(1)
        m_default, m_mapping = self.TABLE
        try:
            l_default, l_mapping = m_mapping[self.msb]
        except KeyError:
            self.value = m_default
        else:
            self.value = l_mapping.get(self.lsb, l_default)


class WrappedReverbType(WrappedReverbChorus):
    # Reverb Type, F0 43 1n 4C 02 01 00 mm ll F7
    type = "reverb"
    REGEX = re.compile(rb'\x43[\x10-\x1F]\x4C\x02\x01\x00\x00(..)', re.S)
    TABLE = (ReverbType.OFF, {
        0x01: (ReverbType.HALL1, {
            0x10: ReverbType.HALL2,
            0x11: ReverbType.HALL3,
        }),
        0x02: (ReverbType.ROOM, {
            0x11: ReverbType.ROOM1,
            0x13: ReverbType.ROOM2,
        }),
        0x03: (ReverbType.STAGE, {
            0x10: ReverbType.STAGE1,
            0x11: ReverbType.STAGE2,
        }),
        0x04: (ReverbType.PLATE, {
            0x10: ReverbType.PLATE1,
            0x11: ReverbType.PLATE2,
        }),
    })


class WrappedChorusType(WrappedReverbChorus):
    # Chorus Type, F0 43 1n 4C 02 01 20 mm ll F7
    type = "chorus"
    REGEX = re.compile(rb'\x43[\x10-\x1F]\x4C\x02\x01\x00\x20(..)', re.S)
    TABLE = (ChorusType.OFF, {
        0x40: (ChorusType.THRU, {}),
        0x41: (ChorusType.CHORUS, {
            0x02: ChorusType.CHORUS2
        }),
        0x42: (ChorusType.CELESTE, {
            0x11: ChorusType.CHORUS1
        }),
        0x43: (ChorusType.FLANGER, {
            0x08: ChorusType.FLANGER1,
            0x11: ChorusType.FLANGER2
        })
    })



def wrap_sysex(message):

    # Put the data into a bytes object so we can regex it
    data = bytes(message.data)
    # Match one by one
    for sysex_class in (WrappedGMSystemOn, WrappedMIDIMasterVolume,
            WrappedMIDIMasterTuning, WrappedReverbType, WrappedChorusType):
        match = sysex_class.REGEX.fullmatch(data)
        if match is not None:
            return sysex_class(message, match)
    # if not, just wrap it generically
    return WrappedSysEx(message)


class WrappedControlChange(WrappedMessage):
    type = "control_change"

    def __init__(self, message):
        super().__init__(self, message)
        self.channel = message.channel
        self.control = message.control
        self.control_value = message.value
        self._process(self.control_value)
    
    def _process(self, value):
        pass


class WrappedLocal(WrappedControlChange):
    type = "local"
    CONTROL = 0x7A

    def _process(self, value):
        # highest bit: 1 for ON, 0 for OFF.
        self.local = value >= 64


def wrap_control(message):
    for control_class in (WrappedLocal,):
        if message.control == control_class.CONTROL:
            return control_class(message)
    return WrappedControlChange(message)


class WrappedProgramChange(WrappedMessage):
    type = "program_change"

    def __init__(self, message):
        super().__init__(self, message)
        self.channel = message.channel
        self.program = message.program


def wrap(message):
    if message.type == "program_change":
        return WrappedProgramChange(message)
    elif message.type == "control_change":
        return wrap_control(message)
    elif message.type == "sysex":
        return wrap_sysex(message)
    else:
        return WrappedMessage(message)


