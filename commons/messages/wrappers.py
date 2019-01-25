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
    value = None

    def __init__(self, message):
        """
        Wrap a mido message.
        """
        # I suppose we could use FrozenMessages here,
        # but we are all responsible adults, right?
        self.message = message
    
    @property
    def channel(self):
        try:
            return self.message.channel
        except AttributeError:
            return None

    @property
    def wrap_type_longform(self):
        return longform.get(self.wrap_type)

    @property
    def value_longform(self):
        return self.value

    def __str__(self):
        return " ".join(
            str(i) for i in (
                self.channel, self.wrap_type_longform, self.value_longform)
            if i is not None)

    def __repr__(self):
        return "<{!s} {!r}>".format(self, self.message)


class WrappedGlobalMessage(WrappedMessage):
    # A wrapped message that changes the global state.
    @property
    def channel(self):
        return None


class WrappedSysEx(WrappedGlobalMessage):
    wrap_type = MessageType.SYSEX

    def __init__(self, message, match=None):
        super().__init__(message)
        self._process(match)

    def _process(self, match):
        self.value = None

    @property
    def wrap_type_longform(self):
        if self.wrap_type is MessageType.SYSEX:
            return "[SysEx {}]".format(
                " ".join(format(x, "02X") for x in self.message.data))
        else:
            return super().wrap_type_longform


class WrappedGMSystemOn(WrappedSysEx):
    # GM System ON, F0 7E 7F 09 01 F7
    wrap_type = SysEx.GM_ON
    REGEX = re.compile(rb'\x7E\x7F\x09\x01\xF7', re.S)


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

    @property
    def wrap_type_longform(self):
        if self.wrap_type is MessageType.CONTROL_CHANGE:
            return "[Control {}]".format(self.message.control)
        else:
            return super().wrap_type_longform


    def _process(self):
        self.value = self.message.value



class WrappedSingle(WrappedControlChange):
    TYPES = {
        Control.DATA_INC, Control.DATA_DEC,
        Control.SOUND_OFF, Control.SOUND_OFF_XMONO, Control.SOUND_OFF_XPOLY,
        Control.NOTES_OFF, Control.NOTES_OFF_XOMNIOFF, Control.NOTES_OFF_XOMNION
    }
    def _process(self):
        # No use for the value
        self.value = None

    def __str__(self):
        return "{} {!s}".format(self.channel, self.wrap_type_longform)


class WrappedHighBoolean(WrappedControlChange):
    def _process(self):
        # highest bit: 1 for ON, 0 for OFF.
        self.value = SwitchBool(self.message.value >= 64)

class WrappedPedal(WrappedHighBoolean):
    TYPES = {Control.PEDAL}
       

class WrappedLocal(WrappedGlobalMessage, WrappedHighBoolean):
    TYPES = {Control.LOCAL}
    def __str__(self):
        return "{!s} {}".format(self.wrap_type_longform, self.value)


_CONTROL_WRAP_MAPPING = {t: c
    for c in (WrappedSingle, WrappedPedal, WrappedLocal)
    for t in c.TYPES}


def wrap_control(message):
    control_class = _CONTROL_WRAP_MAPPING.get(
        message.control, WrappedControlChange)
    return control_class(message)


class WrappedProgramChange(WrappedMessage):
    wrap_type = MessageType.PROGRAM_CHANGE

    def __init__(self, message):
        super().__init__(message)
        self.value = message.program


def wrap(message):
    """
    Wrap a message.
    If a message is not of the wrappable type,
    then returns None.
    """
    if message.type == "program_change":
        return WrappedProgramChange(message)
    elif message.type == "control_change":
        return wrap_control(message)
    elif message.type == "sysex":
        return wrap_sysex(message)
    else:
        return WrappedMessage(message)


class StateChange(WrappedMessage):
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

    @property
    def wrap_type_longform(self):
        if self.wrap_type is not None:
            try:
                return longform[self.wrap_type]
            except KeyError:
                pass
        return "[RPN {}]".format(self.rpn)

    def _process(self):
        # Everything uses MSB only
        if self.data[1] is None:
            self.value = self.data[0]
        else:
            self.value = self.data


class VoiceChange(StateChange):
    """
    A StateChange object for when the voice is changed.
    """

    def __init__(self, wrapped, bank_program):
        super().__init__(wrapped)
        self.bank_program = bank_program
        
        assert self.message.program == bank_program[2]

        self.value = voices.from_bank_program_default(*bank_program)
    
    @property
    def value_longform(self):
        return self.value.voice_string_extended()
    
    @property
    def wrap_type_longform(self):
        return "Voice"
