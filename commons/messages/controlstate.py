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

import collections.abc

import mido

from ..values import (
    ReverbType, ReverbCodes, ChorusType, ChorusCodes,
    SwitchBool, AcmpSection, NoteValue)
from .wrappers import (
    MessageType, Control, Rpn, SysEx, SeqSpec, Special,
    UnknownControl, UnknownSysEx, UnknownRpn, UnknownSeqSpec,
    RpnDataCombo, NoteEvent, bonus_strings, Bonus,
    WrappedMessage, WrappedChannelMessage, GuideTracks)
from . import voices, exclusives, styles, chords
from .. import util


class DispatchDict(dict):
    """
    A subclass of dict that has a decorator
    that can assigns the decorated function to keys in the dict
    """
    # Dict subclass
    def register(self, *keys):
        """
        A decorator that assigns the decorated function to the
        provided key(s)
        """
        # decorator...
        def register_func(action):
            for key in keys:
                self[key] = action
            return action
        return register_func


# should I implement the mutable mapping abc?
class MidiState(collections.abc.Mapping):
    DICT_SLOTS = frozenset()

    def __init__(self):
        self._dict = {key: None for key in self.DICT_SLOTS}

    def reset_blank(self):
        """
        Set every key's value to None
        """
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
            raise KeyError(key)

    def __contains__(self, key):
        return key in self.DICT_SLOTS

    def __iter__(self):
        return iter(self.DICT_SLOTS)

    def __len__(self):
        return len(self.DICT_SLOTS)


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

    # Special Controllers, which we pass through
    SPECIAL_CONTROLLERS = frozenset((
        Control.PORTAMENTO_CTRL,
        Control.VARIATION
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

    # For the User Song channels, we need to keep track of the Octave message,
    # which is relayed as a polytouch message for some reason.
    US_MESSAGE_TYPES = frozenset((
        "polytouch",
    ))

    # RECOGNISED_MESSAGE_TYPES = (
    #     CONTROL_MESSAGE_TYPES | NOTE_MESSAGE_TYPES | US_MESSAGE_TYPES
    # )

    REG_CONTROLLERS = (
        BANK_CONTROLLERS | CONT_CONTROLLERS | RPN_CONTROLLERS
    )

    DICT_SLOTS = (
        REG_CONTROLLERS | SWITCH_CONTROLLERS |
        OFFSET_CONTROLLERS | RPNS |
        {
            Control.DATA_MSB,
            MessageType.PROGRAM_CHANGE,
            MessageType.PITCHWHEEL,
            Special.OCTAVE,
        }
    )
    # We don't really need to keep track of Portamento Control,
    # for now, because it only affects 1 note really.

    def __init__(self, channel, user_song=False):
        """
        The channel parameter should be the channel number (0-15).
        """
        super().__init__()

        self._channel = channel
        self.user_song = user_song

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
        try:
            method = self._MESSAGE_TYPE_DISPATCHER[message.type]
        except KeyError:
            # Pass through 'silently'
            return None
        else:
            # Call the method
            return method(self, message)
    
    # Message Type handling
    _MESSAGE_TYPE_DISPATCHER = DispatchDict()

    @_MESSAGE_TYPE_DISPATCHER.register(*NOTE_MESSAGE_TYPES)
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

    @_MESSAGE_TYPE_DISPATCHER.register("control_change")
    def _handle_control(self, message):
        try:
            control_type = Control(message.control)
        except ValueError:
            # Unknown Control
            control_type = UnknownControl(message.control)
            return WrappedChannelMessage(
                message, control_type, message.value)        
        try:
            method = self._CONTROL_DISPATCHER[control_type]
        except KeyError:
            # Shouldn't happen but just in case
            raise ValueError("Unrecognised message: {}".format(message))
        else:
            return method(self, message, control_type)    

    @_MESSAGE_TYPE_DISPATCHER.register("program_change")
    def _handle_program_change(self, message):
        # Do we report a no-change?
        voice = self._change_program(message.program)
        return WrappedChannelMessage(
            message, MessageType.PROGRAM_CHANGE, voice)

    @_MESSAGE_TYPE_DISPATCHER.register("pitchwheel")
    def _handle_pitchwheel(self, message):
        self[MessageType.PITCHWHEEL] = message.pitch
        return WrappedChannelMessage(
            message, MessageType.PITCHWHEEL, message.pitch)

    @_MESSAGE_TYPE_DISPATCHER.register(*US_MESSAGE_TYPES)
    def _handle_us(self, message):
        # Very Special Special Case
        if (self.user_song and
                message.type == "polytouch" and
                message.note == 0x00):
            # Octave Offset.
            # It's an offset value from 0x40.
            # (Sneaky reuse of a control handling method here)
            return self._handle_offset(message, Special.OCTAVE)
        else:
            return None
    
    # Control type handling
    _CONTROL_DISPATCHER = DispatchDict()

    @_CONTROL_DISPATCHER.register(*REG_CONTROLLERS)
    def _handle_reg(self, message, control_type):
        # simply set the value.
        return self._set_value(
            message, control_type, message.value)
    
    @_CONTROL_DISPATCHER.register(*SWITCH_CONTROLLERS)
    def _handle_switch(self, message, control_type):
        # map to a switch.
        value = SwitchBool.from_b(message.value)
        return self._set_value(
            message, control_type, value)
    
    @_CONTROL_DISPATCHER.register(*OFFSET_CONTROLLERS)
    def _handle_offset(self, message, control_type):
        # Apply the offset
        value = message.value - 0x40
        return self._set_value(
            message, control_type, value)
    
    @_CONTROL_DISPATCHER.register(Control.DATA_LSB)
    def _handle_data_lsb(self, message, control_type):
        # Don't set anything, just return a wrapped message.
        return WrappedChannelMessage(
            message, control_type, message.value)
    
    @_CONTROL_DISPATCHER.register(Control.DATA_MSB)
    def _handle_data_msb(self, message, control_type):
        # Special MSB RPN handling.
        return self._set_rpn(
            message, control_type, message.value)
    
    @_CONTROL_DISPATCHER.register(Control.DATA_DEC)
    def _handle_data_dec(self, message, control_type):
        return self._set_rpn(
            message, control_type, self[Control.DATA_MSB]-1)
    
    @_CONTROL_DISPATCHER.register(Control.DATA_INC)
    def _handle_data_inc(self, message, control_type):
        return self._set_rpn(
            message, control_type, self[Control.DATA_MSB]+1)
        
    @_CONTROL_DISPATCHER.register(*MODE_CONTROLLERS)
    def _handle_mode(self, message, control_type):
        if control_type is Control.RESET_CONTROLS:
            self.reset_controllers()
        # we don't set anything
        return WrappedChannelMessage(message, control_type, None)
                
    @_CONTROL_DISPATCHER.register(Control.PORTAMENTO_CTRL)
    def _handle_portamento(self, message, control_type):
        # Special case, we don't set anything
        value = NoteValue(message.value)
        return WrappedChannelMessage(message, control_type, value)

    @_CONTROL_DISPATCHER.register(Control.VARIATION)
    def _handle_variation(self, message, control_type):
        # The DGX-505 doesn't support this message, but
        # it's present in recorded user songs.
        # Special case, We just return straight through?
        return WrappedChannelMessage(
            message, control_type, message.value)

    # sub methods for setting the value
    def _set_value(self, message, wrap_type, value):
        self[wrap_type] = value
        return WrappedChannelMessage(message, wrap_type, value)

    def _set_rpn(self, message, wrap_type, msb_value):
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







class MidiControlState(MidiState):
    """
    A class that keeps track of the state of the MIDI controls.
    """
    GENERAL_SETTINGS = frozenset((
        Control.LOCAL,
        SysEx.MASTER_VOL, SysEx.MASTER_TUNE,
        SysEx.REVERB_TYPE, SysEx.CHORUS_TYPE,
    ))

    SONG_SETTINGS = frozenset((
        SeqSpec.STYLE, SeqSpec.STYLE_VOL,
        SeqSpec.SECTION, SeqSpec.CHORD,
        MessageType.TEMPO
    ))
    # We also recognise SysEx.CHORD, but we delegate the
    # slot to SeqSpec.CHORD because it's the same thing.

    DICT_SLOTS = GENERAL_SETTINGS | SONG_SETTINGS

    def __init__(self, wrap_notes=True, user_song=False):
        super().__init__()

        # There are 16 channels, we'll simply use a list to keep track of them
        self._channels = tuple(ChannelState(n, user_song=user_song) for n in range(16))

        # Additionally, we also have the sysex and a few other parameters
        # to keep track of.

        # Should we wrap notes?
        self.wrap_notes = wrap_notes
        # Keep track of the user_song flag
        self.user_song = user_song

        # Unknown: How exactly does the meta-message handling work?
        # Does it need to be on track 0?
        # How about mixing sysex and meta chord changes?

    @property
    def channels(self):
        return self._channels

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
                    message, Control.LOCAL, value,
                    bonus_strings(('n', message.channel, 0x0, '1X')))
            else:
                return self._channels[message.channel].feed(message)
        elif message.type in ChannelState.CONTROL_MESSAGE_TYPES:
            return self._channels[message.channel].feed(message)
        # System Exclusive / Sequencer Specific
        elif message.type in {"sysex", "sequencer_specific"}:
            return self._handle_sysex_seqspec(message)
        # User Song Polytouch Special Handling
        elif self.user_song and message.type in ChannelState.US_MESSAGE_TYPES:
            return self._channels[message.channel].feed(message)
        # Meta Messages.
        elif message.type == "set_tempo":
            # We use the bpm instead of the midi-tempo as value.
            return WrappedMessage(
                message, MessageType.TEMPO, mido.tempo2bpm(message.tempo))
        return None

    _DATA_DISPATCHER = DispatchDict()

    def _handle_sysex_seqspec(self, message):
        matchdict = exclusives.match(message)
        if matchdict:
            try:
                dispatch = self._DATA_DISPATCHER[matchdict['type']]
            except KeyError:
                pass
            else:
                return dispatch(self, message, **matchdict)
        return self._handle_unknown_sysex_seqspec(message)

    @staticmethod
    def _handle_unknown_sysex_seqspec(message):
        if message.type == 'sysex':
            return WrappedMessage(message, UnknownSysEx(message.data))
        elif message.type == 'sequencer_specific':
            return WrappedMessage(message, UnknownSeqSpec(message.data))

    @_DATA_DISPATCHER.register(SysEx.GM_ON)
    def _handle_gm_on(self, message, type):
        assert type is SysEx.GM_ON
        self.reset_gm()
        return WrappedMessage(message, type)

    @_DATA_DISPATCHER.register(SysEx.MASTER_VOL)
    def _handle_midi_master_volume(self, message, type, ll, mm):
        assert type is SysEx.MASTER_VOL
        # MIDI Master Volume.
        # mm used, ll ignored.
        value = mm
        self[type] = value
        return WrappedMessage(message, type, value,
            bonus_strings(
                ('ll', ll, 0x00, '02X')
            ))

    @_DATA_DISPATCHER.register(SysEx.MASTER_TUNE)
    def _handle_midi_master_tuning(self, message, type, n, mm, ll, cc):
        assert type is SysEx.MASTER_TUNE
        m = mm & 0xF
        l = ll & 0xF
        t_val = ((m << 4) | l ) - 0x80
        value = max(-100, min(t_val, +100))  # clamp
        self[type] = value
        return WrappedMessage(message, type, value,
            bonus_strings(
                ('n', n, 0x0, '1X'),
                ('t_val', t_val, value, '+d'),
                ('mh', mm >> 4, 0x0, '1X'),
                ('lh', ll >> 4, 0x0, '1X'),
                ('cc', cc, 0x00, '02X')
            ))

    _EFFECT_CODES = {
        SysEx.REVERB_TYPE: ReverbCodes,
        SysEx.CHORUS_TYPE: ChorusCodes,
    }
    @_DATA_DISPATCHER.register(SysEx.CHORUS_TYPE)
    @_DATA_DISPATCHER.register(SysEx.REVERB_TYPE)
    def _handle_rev_chorus_types(self, message, type, n, mm, ll):
        code_lookup = self._EFFECT_CODES[type]
        value = code_lookup.from_code(mm, ll)
        tm, tl = code_lookup[value]
        self[type] = value
        return WrappedMessage(message, type, value,
            bonus_strings(
                ('n', n, 0x0, '1X'),
                ('mm', mm, tm, '02X'),
                ('ll', ll, tl, '02X'),
            ))

    @_DATA_DISPATCHER.register(SysEx.XG_ON)
    def _handle_xg_on(self, message, type, n):
        assert type is SysEx.XG_ON
        self.reset_gm()
        return WrappedMessage(message, type, None,
            bonus_strings(
                ('n', n, 0x0, '1X')
            ))

    @_DATA_DISPATCHER.register(SysEx.XG_RESET)
    def _handle_xg_reset(self, message, type, n):
        assert type is SysEx.XG_RESET
        self.reset_param()
        return WrappedMessage(message, type, None,
            bonus_strings(
                ('n', n, 0x0, '1X')
            ))

    @_DATA_DISPATCHER.register(SysEx.CHORD, SeqSpec.CHORD)
    def _handle_chord(self, message, type, chordbytes):
        # We use SeqSpec.CHORD as the slot.
        try:
            value = chords.byte_chord(chordbytes)
        except (KeyError, ValueError):
            value = None
        self[SeqSpec.CHORD] = value

        cr, _, bn, _ = chordbytes
        if value is None or cr >> 4 == 0 or bn >> 4 == 0:
            bonus = Bonus([('chordbytes', util.hexspace(chordbytes))])
        else:
            bonus = None
        return WrappedMessage(message, type, value, bonus)

    @_DATA_DISPATCHER.register(SeqSpec.STYLE)
    def _handle_style(self, message, type, ss):
        assert type is SeqSpec.STYLE
        # ss is the style number, minus 1.
        try:
            value = styles.from_number(ss+1)
            bonus = None
        except KeyError:
            value = None
            bonus = Bonus([('ss', format(ss, '02X'))])
        self[SeqSpec.STYLE] = value
        return WrappedMessage(message, type, value, bonus)

    @_DATA_DISPATCHER.register(SeqSpec.STYLE_VOL)
    def _handle_style_vol(self, message, type, vv):
        assert type is SeqSpec.STYLE_VOL
        value = vv
        self[SeqSpec.STYLE_VOL] = value
        return WrappedMessage(message, type, value)

    @_DATA_DISPATCHER.register(SeqSpec.SECTION)
    def _handle_section(self, message, type, ss):
        assert type is SeqSpec.SECTION
        try:
            value = AcmpSection(ss)
            bonus = None
        except KeyError:
            value = None
            bonus = Bonus([('ss', format(ss, '02X'))])
        self[SeqSpec.SECTION] = value
        return WrappedMessage(message, type, value, bonus)



    @_DATA_DISPATCHER.register(SeqSpec.GUIDE_TRACK)
    def _handle_guide(self, message, type, rr, ll):
        assert type is SeqSpec.GUIDE_TRACK
        try:
            value = GuideTracks.from_rl_bytes(rr, ll)
            bonus = None
        except ValueError:
            value = None
            bonus = Bonus([('rr', format(rr, '02X'),
                           'll', format(ll, '02X'))])
        return WrappedMessage(message, type, value, bonus)

    @_DATA_DISPATCHER.register(SeqSpec.XF_VERSION)
    def _handle_xf(self, message, type, k, l, s, i):
        assert type is SeqSpec.XF_VERSION
        value = Bonus([
            ('Karaoke', k),
            ('Lyrics', l),
            ('Style', s),
            ('Info', i)
        ])
        return WrappedMessage(message, type, value)


    # def _dump(self):
    #     for x, y in self._iter_values():
    #         print('{}: {}'.format(x, y))