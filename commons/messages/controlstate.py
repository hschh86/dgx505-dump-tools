"""
controlstate.py

Keeping track of the control messages!
"""

# We want to keep track of the state of the controls.
# purely as a visual aid.
# In theory, we feed in the messages to both an actual MIDI instrument
# and this module helpfully keeps track of what the
# instrument sees.

# We don't need to keep track of everything, just the interesting bits:
# the control changes, program changes, and some of the SysEx.
# No need for every single note!

# There are 16 channels. Humans read them as 1 to 16, but internally
# they're 0 to 15, or 0x0 to 0xF.

# Each channel has 128 controls that can be set,
# each with a value from 0 to 127.
# There are also the programs for each channel (0-127).
# Some settings are set with two different controls, one for MSB and LSB.
# Even further, there is the RPN settings, which are themselves set using
# multiple channel settings.
# The SysEx messages supported by the DGX-505 can also change state,
# for all channels. (so it appears at the instrument level.)
#  So there's a lot to keep track of.

# (For more information consult the DGX505Midi.md document)

from ..values import ChorusType, ReverbType, SwitchBool, NoteValue
from .wrappers import (MessageType, Control, Rpn, SysEx,
    UnknownControl, UnknownSysEx, UnknownRpn,
    RpnDataCombo, NoteEvent, WrappedMessage, WrappedChannelMessage)
from . import voices


# should I implement the mutable mapping abc?
class MidiState(object):
    DICT_SLOTS = frozenset()

    def __init__(self):
        self._dict = {key: None for key in self.DICT_SLOTS}

    def reset_blank(self):
        self._dict.update((key, None) for key in self._dict)

    def update(self, pairs):
        # I may want to change this so it supports the full
        # update from abc
        for key, value in pairs:
            self[key] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        if key in self.DICT_SLOTS:
            self._dict[key] = value
        else:
            raise KeyError("Unknown Key: {}".format(key))

    def __contains__(self, key):
        return key in self.DICT_SLOTS


class ChannelState(MidiState):
    """
    A class that keeps track of the state of the controls of a channel.
    """

    # There are different types of controllers:
    # Bank, which works with the program change.
    BANK_CONTROLLERS = frozenset((
        Control.BANK_MSB, Control.BANK_LSB,
    ))

    # Regular continuous controllers and effect level controllers
    # which take ordinary values 0-127.
    CONT_CONTROLLERS = frozenset((
        Control.VOLUME, Control.PAN,
        Control.MODULATION, Control.EXPRESSION,
        Control.REVERB, Control.CHORUS,
    ))

    # Switches And Pedals, which take ON/OFF
    SWITCH_CONTROLLERS = frozenset((
        Control.PEDAL,
    ))

    # Sound Controllers, which take offset values. -64 to +63.
    OFFSET_CONTROLLERS = frozenset((
        Control.HARMONIC, Control.RELEASE,
        Control.ATTACK, Control.BRIGHTNESS,
    ))

    # The RPN controls.
    RPN_CONTROLLERS = frozenset((
        Control.RPN_MSB, Control.RPN_LSB,
    ))

    # The Data Controls.
    DATA_CONTROLLERS = frozenset((
        Control.DATA_MSB, Control.DATA_LSB,
        Control.DATA_INC, Control.DATA_DEC,
    ))

    # The Very Special Portamento Controller
    SPECIAL_CONTROLLERS = frozenset((
        Control.PORTAMENTO_CTRL,
    ))

    # The Special Channel Mode Messages.
    SOUNDOFF_CONTROLLERS = frozenset((
        Control.SOUND_OFF,
        Control.SOUND_OFF_XMONO,
        Control.SOUND_OFF_XPOLY,
    ))

    NOTESOFF_CONTROLLERS = frozenset((
        Control.NOTES_OFF,
        Control.NOTES_OFF_XOMNIOFF,
        Control.NOTES_OFF_XOMNION,
    ))

    MODE_CONTROLLERS = (
        SOUNDOFF_CONTROLLERS |
        NOTESOFF_CONTROLLERS |
        {Control.RESET_CONTROLS}
    )

    # We also have RPNS. (not including NULL here.)
    RPNS = frozenset((
        Rpn.PITCH_BEND_RANGE, Rpn.FINE_TUNE, Rpn.COARSE_TUNE,
    ))

    CONTROL_MESSAGE_TYPES = frozenset((
        "control_change",
        "program_change",
        "pitchwheel"
    ))

    NOTE_MESSAGE_TYPES = frozenset((
        "note_on",
        "note_off",
    ))

    RECOGNISED_MESSAGE_TYPES = (
        CONTROL_MESSAGE_TYPES | NOTE_MESSAGE_TYPES
    )

    REG_CONTROLLERS = (
        BANK_CONTROLLERS | CONT_CONTROLLERS | RPN_CONTROLLERS
    )

    DICT_SLOTS = (
        REG_CONTROLLERS | SWITCH_CONTROLLERS |
        OFFSET_CONTROLLERS | RPNS |
        {
            Control.DATA_MSB,
            MessageType.PROGRAM_CHANGE,
            MessageType.PITCHWHEEL
        }
    )
    # We don't really need to keep track of Portamento Control,
    # for now, because it only affects 1 note really.

    def __init__(self, channel):
        """
        The channel parameter should be the channel number (0-15).
        """
        super().__init__()

        self._channel = channel

    def reset_controllers(self):
        # The method that gets called upon Reset Controllers message.
        self.update((
            (MessageType.PITCHWHEEL, 0),
            (Control.MODULATION, 0),
            (Control.EXPRESSION, 127),
            (Control.PEDAL, SwitchBool.OFF),
            (Control.HARMONIC, 0),
            (Control.RELEASE, 0),
            (Control.ATTACK, 0),
            (Control.BRIGHTNESS, 0),
            (Control.RPN_MSB, 0x7F),
            (Control.RPN_LSB, 0x7F),
            #(Control.PORTAMENTO_CTRL, None),
        ))

    def reset_gm(self):
        # The method that gets called upon GM_ON, etc.
        self.reset_controllers()
        self.update((
            (Control.BANK_LSB, 0),
            (Rpn.PITCH_BEND_RANGE, 2),
            (Rpn.FINE_TUNE, 0),
            (Rpn.COARSE_TUNE, 0),
            (Control.VOLUME, 100),
            (Control.PAN, 64),
            (Control.REVERB, 40),
            (Control.CHORUS, 0),
        ))
        # Channel 9 (10) is the rhythm channel
        if self._channel == 9:
            self[Control.BANK_MSB] = 0x7F
        else:
            self[Control.BANK_MSB] = 0
        self._change_program(0)

    def _change_program(self, program):
        msb, lsb = self.bank()
        voice = voices.from_bank_program_default(msb, lsb, program)
        if voice is not None:
            self[MessageType.PROGRAM_CHANGE] = voice
        return voice

    def reset_poweron(self):
        # The power on state.
        self.reset_gm()
        # This is the one with the data msb thing.
        self[Control.DATA_MSB] = 0

    def bank(self):
        return self[Control.BANK_MSB], self[Control.BANK_LSB]

    def rpn(self):
        rpn = self[Control.RPN_MSB], self[Control.RPN_LSB]
        try:
            return Rpn(rpn)
        except ValueError:
            return UnknownRpn(rpn)

    def bank_program(self):
        return self[MessageType.PROGRAM_CHANGE]

    def get_rpn_data(self, rpn):
        if rpn in self.RPNS:
            return self[rpn]
        else:
            return None

    def feed(self, message):
        # Feed In a Mido Message.
        if message.channel != self._channel:
            raise ValueError("Incorrect channel: {}".format(message))

        if message.type not in self.RECOGNISED_MESSAGE_TYPES:
            # Pass through 'silently'
            return None

        if message.type in self.NOTE_MESSAGE_TYPES:
            return self._handle_note(message)
        elif message.type == "control_change":
            return self._handle_control(message)
        elif message.type == "program_change":
            # Do we report a no-change?
            voice = self._change_program(message.program)
            return WrappedChannelMessage(
                message, MessageType.PROGRAM_CHANGE, voice)
        elif message.type == "pitchwheel":
            self[MessageType.PITCHWHEEL] = message.pitch
            return WrappedChannelMessage(
                message, MessageType.PITCHWHEEL, message.pitch)

        # Shouldn't fall through here
        raise ValueError("Unrecognised message: {}".format(message))

    def _handle_note(self, message):
        # Wrap note_on and note_off.
        # We don't keep track of them, we just wrap them
        # possibly appropriately to the voice, but not
        # necessarily.
        note_type = NoteEvent(NoteValue(message.note))
        if message.type == "note_off":
            value = 0
        else:
            value = message.velocity
        return WrappedChannelMessage(message, note_type, value)

    def _handle_control(self, message):
        try:
            control_type = Control(message.control)
        except ValueError:
            # Unknown Control
            control_type = UnknownControl(message.control)
            return WrappedChannelMessage(
                message, control_type, message.value)

        # Regular Values.
        # (Do we handle the bank/rpn separately?)
        if control_type in self.REG_CONTROLLERS:
            # Simply set the value to the value.
            return self._set_value(
                control_type, message.value, message)
        elif control_type in self.SWITCH_CONTROLLERS:
            # We need to map to a switch
            return self._set_value(
                control_type, SwitchBool.from_b(message.value), message)
        elif control_type in self.OFFSET_CONTROLLERS:
            # Apply the offset
            return self._set_value(
                control_type, message.value - 0x40, message)
        elif control_type in self.DATA_CONTROLLERS:
            if control_type is Control.DATA_LSB:
                # For LSB, don't set anything.
                # Just return a wrapped message.
                return WrappedChannelMessage(
                    message, control_type, message.value)
            # Else, we hand over to special MSB RPN handling
            elif control_type is Control.DATA_MSB:
                return self._set_rpn(
                    control_type, message.value, message)
            elif control_type is Control.DATA_DEC:
                return self._set_rpn(
                    control_type, self[Control.DATA_MSB]-1, message)
            elif control_type is Control.DATA_INC:
                return self._set_rpn(
                    control_type, self[Control.DATA_MSB]+1, message)
        elif control_type in self.MODE_CONTROLLERS:
            if control_type is Control.RESET_CONTROLS:
                self.reset_controllers()
            # we don't set anything
            return WrappedChannelMessage(message, control_type, None)
        elif control_type is Control.PORTAMENTO_CTRL:
            # Special case, we don't set anything
            value = NoteValue(message.value)
            return WrappedChannelMessage(message, control_type, value)
        # We shouldn't fall through here
        raise ValueError("Unrecognised message: {}".format(message))

    def _set_value(self, wrap_type, value, message):
        self[wrap_type] = value
        return WrappedChannelMessage(message, wrap_type, value)

    def _set_rpn(self, wrap_type, msb_value, message):
        rpn = self.rpn()
        if 0x00 <= msb_value <= 0x7F:
            # we have a valid value.
            # First, we set the most recent MSB to this value
            # (It doesn't make much sense, but it's the way
            # that the DGX-505 seems to do it)
            self[Control.DATA_MSB] = msb_value
            # Then, we have to interpret the result.
            if rpn in self.RPNS:
                # Known RPN.
                if rpn is Rpn.PITCH_BEND_RANGE:
                    # This is as-is, although should we clamp?
                    value = msb_value
                else:
                    # Fine or coarse tune, an offset.
                    value = msb_value - 0x40
                self[rpn] = value
            else:
                # Unknown or Null RPN.
                value = None
        else:
            # The value doesn't get set, so should we wrap the
            # message with the current value of the current rpn?
            value = None
        return WrappedChannelMessage(
            message, RpnDataCombo(wrap_type, rpn), value)



    # def _iter_values(self):
    #     yield ("Bank Program", self._bank_program)
    #     for k, v in self._controls.items():
    #         yield (str(k), v)
    #     for k in self._data_msb:
    #         yield (str(k), (self._data_msb[k], self._data_lsb[k]))
    #     yield ("Pitchwheel", self._pitchwheel)


class MidiControlState(MidiState):
    """
    A class that keeps track of the state of the MIDI controls.
    """

    DICT_SLOTS = frozenset((
        Control.LOCAL,
        SysEx.MASTER_VOL, SysEx.MASTER_TUNE,
        SysEx.REVERB_TYPE, SysEx.CHORUS_TYPE,
    ))

    def __init__(self, wrap_notes=True):
        super().__init__()

        # There are 16 channels, we'll simply use a list to keep track of them
        self._channels = [ChannelState(n) for n in range(16)]

        # Additionally, we also have the sysex and a few other parameters
        # to keep track of.

        # Should we wrap notes?
        self.wrap_notes = wrap_notes

    def reset_gm(self):
        self.update((
            (SysEx.REVERB_TYPE, ReverbType.HALL1),
            (SysEx.CHORUS_TYPE, ChorusType.CHORUS),
            (SysEx.MASTER_VOL, 0x7F),
        ))
        for channel in self._channels:
            channel.reset_gm()

    def reset_param(self):
        self.reset_gm()
        self[SysEx.MASTER_TUNE] = 0

    def local(self, switch):
        if switch not in SwitchBool:
            switch = SwitchBool(switch)
        self[Control.LOCAL] = switch

    def feed(self, message):
        """
        Feed a mido message into the object, updating the internal state.
        Returns wrapped message
        """
        if (self.wrap_notes and
                message.type in ChannelState.NOTE_MESSAGE_TYPES):
            return self._channels[message.channel].feed(message)
        elif message.type == "control_change":
            if message.control == Control.LOCAL.value:
                # LOCAL message.
                value = SwitchBool.from_b(message.value)
                self.local(value)
                return WrappedMessage(
                    message, Control.LOCAL, value)
            else:
                return self._channels[message.channel].feed(message)
        elif message.type in ChannelState.CONTROL_MESSAGE_TYPES:
            return self._channels[message.channel].feed(message)
        elif message.type == "sysex":
            return self._handle_sysex(message)
        return None

    def _handle_sysex(self, message):
        sysex_type = None
        value = None
        data = message.data
        if data == (0x7E, 0x7F, 0x09, 0x01):
            # GM System ON
            # F0 7E 7F 09 01 F7
            sysex_type = SysEx.GM_ON
            self.reset_gm()

        elif (len(data) == 6 and
              data[:4] == (0x7F, 0x7F, 0x04, 0x01)):
            # MIDI Master Volume
            # F0 7F 7F 04 01 xx mm F7
            sysex_type = SysEx.MASTER_VOL
            value = data[5]

        elif (data[0] == 0x43 and data[1] >> 4 == 1):
            # Yamaha Exclusive Messages F0 43 1x .. F7
            if (len(data) < 9 and data[2] == 0x4C):
                # XG Parameter Change
                # F0 43 1x 4C .. F7
                a, b = data[3:5], data[5:]
                if len(b) == 3 and a == (0x02, 0x01):
                    # Chorus/Reverb
                    # F0 43 1x 4C 02 01 tt mm ll F7
                    tt, mm, ll = b
                    if tt == 0x00:
                        # Reverb type.
                        sysex_type = SysEx.REVERB_TYPE
                        value = ReverbType.from_b(mm, ll)

                    elif tt == 0x20:
                        # Chorus Type
                        sysex_type = SysEx.CHORUS_TYPE
                        value = ChorusType.from_b(mm, ll)

                elif len(b) == 2 and a == (0x00, 0x00):
                    if b == (0x7E, 0x00):
                        # XG System On
                        # F0 43 1x 4C 00 00 7E 00 F7
                        sysex_type = SysEx.XG_ON
                        self.reset_gm()

                    elif b == (0x7F, 0x00):
                        # XG All Parameter Reset
                        # F0 43 1x 4C 00 00 7F 00 F7
                        sysex_type = SysEx.XG_RESET
                        self.reset_param()

            elif (len(data) == 9 and
                data[2:6] == (0x27, 0x30, 0x00, 0x00)):
                # MIDI Master Tuning
                # F0 43 1x 27 30 00 00 xm xl xx F7
                sysex_type = SysEx.MASTER_TUNE
                mm, ll = data[6:8]
                ml = ((mm & 0xF) << 4) | (ll & 0xF)
                # clamp to [-100, +100]
                value = max(-100, min(ml - 0x80, +100))

        if sysex_type is None:
            sysex_type = UnknownSysEx(message.data)
        else:
            if value is not None:
                self[sysex_type] = value

        return WrappedMessage(
            message, sysex_type, value)


    # def _iter_values(self):
    #     yield "Local", self._local
    #     yield "Master volume", self._master_vol
    #     yield "Master tuning", self._master_tune
    #     yield "Reverb type", self._reverb
    #     yield "Chorus type", self._chorus
    #     for channel in self._channels:
    #         yield "CHANNEL", channel._channel
    #         yield from channel._iter_values()

    # def _dump(self):
    #     for x, y in self._iter_values():
    #         print('{}: {}'.format(x, y))