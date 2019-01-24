"""
wrappers.py

Wrappers for mido messages.

The intent of these is to have a more friendly way of
displaying and working with control and sysex messages.
"""
# I'm not sure if that goal is achieved. May have gone overboard with classes

# Should these be wrappers, subclasses, or entirely different???
import re

from .controls import MessageType, Control, Rpn, SysEx, longform
from ..enums import ReverbType, ChorusType, SwitchBool
from . import voices

class WrappedMessage(object):
    # These are wrapped mido messages.
    # Like normal messages, but with some extra metadata.
    wrap_type = None

    def __init__(self, message):
        """
        Wrap a mido message.
        """
        # I suppose we could use FrozenMessages here,
        # but we are all responsible adults, right?
        self.message = message

    @property
    def wrap_type_longform(self):
        return longform.get(self.wrap_type)

    def __str__(self):
        return "{!s} {!s}".format(self.wrap_type_longform, self.message)

    def __repr__(self):
        return "<{!s} {!r}>".format(self, self.message)


class WrappedGlobalMessage(WrappedMessage):
    # A wrapped message that changes the global state.
    @property
    def channel(self):
        return None


class WrappedChannelMessage(WrappedMessage):
    # A wrapped message that changes a channel state.
    @property
    def channel(self):
        return self.message.channel


class WrappedSysEx(WrappedGlobalMessage):
    wrap_type = MessageType.SYSEX

    def __init__(self, message, match=None):
        super().__init__(message)
        self._process(match)

    def _process(self, match):
        self.value = self.message.data

    def __str__(self):
        return "{!s} value={}".format(self.wrap_type, self.value)


class WrappedGMSystemOn(WrappedSysEx):
    # GM System ON, F0 7E 7F 09 01 F7
    wrap_type = SysEx.GM_ON
    REGEX = re.compile(rb'\x7E\x7F\x09\x01\xF7', re.S)

    def _process(self, match):
        self.value = None

    def __str__(self):
        return str(self.wrap_type)


class WrappedMIDIMasterVolume(WrappedSysEx):
    # MIDI Master Volume, F0 7F 7F 04 01 ** mm F7
    wrap_type = SysEx.MASTER_VOL
    REGEX = re.compile(rb'\x7F\x7F\x04\x01.(.)', re.S)
    def _process(self, match):
        self.value, = match.group(1)


class WrappedMIDIMasterTuning(WrappedSysEx):
    # MIDI Master Tuning, F0 43 1* 27 30 00 00 *m *l ** F7
    wrap_type = SysEx.MASTER_TUNE
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
    REGEX = re.compile(rb'\x43[\x10-\x1F]\x4C\x02\x01([\x00\x20]..)', re.S)
    def _process(self, match):
        cat, self.msb, self.lsb = match.group(1)
        if cat == 0x00:
            self.wrap_type = SysEx.REVERB_TYPE
            self.value = ReverbType.from_b(self.msb, self.lsb)
        elif cat == 0x20:
            self.wrap_type = SysEx.CHORUS_TYPE
            self.value = ChorusType.from_b(self.msb, self.lsb)


def wrap_sysex(message):

    # Put the data into a bytes object so we can regex it
    data = bytes(message.data)
    # Match one by one
    for sysex_class in (WrappedGMSystemOn, WrappedMIDIMasterVolume,
            WrappedMIDIMasterTuning, WrappedReverbChorus):
        match = sysex_class.REGEX.fullmatch(data)
        if match is not None:
            return sysex_class(message, match)
    # if not, just wrap it generically
    return WrappedSysEx(message)


class WrappedControlChange(WrappedMessage):
    wrap_type = MessageType.CONTROL_CHANGE
    def __init__(self, message):
        super().__init__(message)

        try:
            self.wrap_type = Control(self.message.control)
        except ValueError:
            pass

        self._process()

    def _process(self):
        self.value = self.message.value


class WrappedChannelControlChange(WrappedChannelMessage, WrappedControlChange):
    def __str__(self):
        return "{} {!s} {}".format(self.channel, self.wrap_type, self.value)


class WrappedSingle(WrappedChannelMessage, WrappedControlChange):
    TYPES = {
        Control.DATA_INC, Control.DATA_DEC,
        Control.SOUND_OFF, Control.SOUND_OFF_XMONO, Control.SOUND_OFF_XPOLY,
        Control.NOTES_OFF, Control.NOTES_OFF_XOMNIOFF, Control.NOTES_OFF_XOMNION
    }
    def _process(self):
        # No use for the value
        self.value = None

    def __str__(self):
        return "{} {!s}".format(self.channel, self.wrap_type)


class WrappedHighBoolean(WrappedControlChange):
    def _process(self):
        # highest bit: 1 for ON, 0 for OFF.
        self.value = SwitchBool(self.message.value >= 64)

class WrappedPedal(WrappedHighBoolean, WrappedChannelControlChange):
    TYPES = {Control.PEDAL}
       

class WrappedLocal(WrappedGlobalMessage, WrappedHighBoolean):
    TYPES = {Control.LOCAL}
    def __str__(self):
        return "{!s} {}".format(self.wrap_type, self.value)


_CONTROL_WRAP_MAPPING = {t: c
    for c in (WrappedSingle, WrappedPedal, WrappedLocal)
    for t in c.TYPES}


def wrap_control(message):
    control_class = _CONTROL_WRAP_MAPPING.get(
        message.control, WrappedChannelControlChange)
    return control_class(message)


class WrappedProgramChange(WrappedChannelMessage):
    wrap_type = MessageType.PROGRAM_CHANGE

    def __init__(self, message):
        super().__init__(message)
        self.value = message.program

    def __str__(self):
        return "{} program {}".format(self.channel, self.value)


def wrap(message):
    if message.type == "program_change":
        return WrappedProgramChange(message)
    elif message.type == "control_change":
        return wrap_control(message)
    elif message.type == "sysex":
        return wrap_sysex(message)
    else:
        return WrappedMessage(message)


class StateChange(object):
    """
    This class is for special wrappers in the control-state thing.
    The wrappers wrap a wrapper itself. This wrapper is the wrapper
    that triggered the shape change.
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped
    
    @property
    def message(self):
        return self.wrapped.message
    
    @property
    def channel(self):
        return self.wrapped.channel


class DataChange(StateChange):
    """
    StateChange object for when some rpn data is set.
    """

    def __init__(self, wrapped, rpn, data):
        super().__init__(wrapped)
        self.rpn = rpn
        self.data = data

        try:
            self.wrap_type = Rpn(rpn)
        except ValueError:
            self.wrap_type = None

        self._process()

    def _process(self):
        self.value = self.data

    def __str__(self):
        return "ch {}, {}, {}".format(self.channel, self.wrap_type, self.value)


class VoiceChange(StateChange):
    """
    A StateChange object for when the voice is changed.
    """

    def __init__(self, wrapped, bank_program):
        super().__init__(wrapped)
        self.bank_program = bank_program
        
        assert self.message.program == bank_program[2]

        try:
            self.voice = voices.from_bank_program(*bank_program)
            self.voice_string = self.voice.voice_string()
        except KeyError:
            self.voice = None
            self.voice_string = str(self.bank_program)

    def __str__(self):
        return "ch {}, Voice {}".format(self.channel, self.voice_string)
