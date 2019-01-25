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

import re

from ..enums import ChorusType, ReverbType
from ..util import assert_low
from .controls import MessageType, Control, Rpn, SysEx
from . import wrappers


class ChannelState(object):
    """
    A class that keeps track of the state of the controls of a channel.
    """
    def __init__(self, channel):
        """
        The channel parameter should be the channel number (0-15).
        """
        self._channel = channel

        # For simplicity, everything gets stored in dictionaries,
        # We have one for controls and two for the RPN data settings.
        self._controls = {c: None for c in Control}
        # The controls one should be keyed by the numbers
        self._data_msb = {n: None for n in Rpn}
        self._data_lsb = {n: None for n in Rpn}
        # and the rpn data ones by an (msb, lsb) tuple.

        # I don't know how the rpn and increment works so I just do them
        # independently with 2 separate dicts. Simple.

        # We also need to keep the state of the program:
        self._bank_program = (None, None, None)
        # Bank MSB, Bank LSB, Program, as bytes.
        # and that's basically it.

    def bank(self):
        return self._controls[Control.BANK_MSB], self._controls[Control.BANK_LSB]

    def rpn(self):
        rpn = self._controls[Control.RPN_MSB], self._controls[Control.RPN_LSB]
        try:
            return Rpn(rpn)
        except ValueError:
            return rpn

    def bank_program(self):
        return self._bank_program


    def feed_wrapped(self, wrapped):
        assert wrapped.channel == self._channel

        # is it a program change?
        
        if wrapped.wrap_type is MessageType.PROGRAM_CHANGE:
            # When the program is set, we save the current bank
            # and the program.
            self._bank_program = (*self.bank(), wrapped.value)
            return wrappers.VoiceChange(wrapped, self._bank_program)

        # Is it a data entry?
        if wrapped.wrap_type in {
            Control.DATA_MSB, Control.DATA_LSB,
            Control.DATA_INC, Control.DATA_DEC,
        }:
            rpn = self.rpn()

            # If we don't know the current rpn, we can't do anything
            # so we just return right away
            if rpn[0] is None or rpn[1] is None:
                return wrapped

            # If we do know the rpn, then augment accordingly
            if wrapped.wrap_type is Control.DATA_MSB:
                self._data_msb[rpn] = wrapped.value
            elif wrapped.wrap_type is Control.DATA_LSB:
                self._data_lsb[rpn] = wrapped.value
            else:
                msb = self._data_msb[rpn]
                if wrapped.wrap_type is Control.DATA_INC:
                    if msb < 0x7F:
                        self._data_msb[rpn] = msb+1
                elif wrapped.wrap_type is Control.DATA_DEC:
                    if msb > 0x00:
                        self._data_msb[rpn] = msb-1
            return wrappers.DataChange(wrapped, rpn, self.data())

        # It's a normal control
        self._controls[wrapped.message.control] = wrapped.value
        return wrapped

    def get_rpn_data(self, rpn):
        return self._data_msb[rpn], self._data_lsb[rpn]

    def data(self):
        return self.get_rpn_data(self.rpn())

    def control_value(self, control):
        return self._controls[control]



class MidiControlState(object):
    """
    A class that keeps track of the state of the MIDI controls.
    """

    def __init__(self):
        # There are 16 channels, we'll simply use a list to keep track of them
        self._channels = [ChannelState(n) for n in range(16)]

        # Additionally, we also have the sysex and a few other parameters
        # to keep track of.

        self._local = None
        self._master_vol = None
        self._master_tune = None
        self._reverb = None
        self._chorus = None


    def feed_message(self, msg):
        """
        Feed a mido message into the object, updating the internal state.
        Returns wrapped message
        """
        wrapped = wrappers.wrap(msg)
        if wrapped.wrap_type is None:
            return wrapped

        if wrapped.channel is None:
            # Global Settings.
            if wrapped.wrap_type is Control.LOCAL:
                self._local = wrapped.value
            elif wrapped.wrap_type is SysEx.GM_ON:
                # TODO: Find a way to reset to default values.
                # whatever they are.
                self.gm_reset()
            elif wrapped.wrap_type is SysEx.MASTER_VOL:
                self._master_vol = wrapped.value
            elif wrapped.wrap_type is SysEx.MASTER_TUNE:
                self._master_tune = wrapped.value
            elif wrapped.wrap_type is SysEx.REVERB_TYPE:
                self._reverb = wrapped.value
            elif wrapped.wrap_type is SysEx.CHORUS_TYPE:
                self._chorus = wrapped.value
            return wrapped
        else:
            # Channel Setting.
            # pass message through.
            return self._channels[wrapped.channel].feed_wrapped(wrapped)

    def gm_reset(self):
        # TODO: What are the default values?

        # "Automatically restores all default settings
        #  except Master Tuning" -- Manual

        # Reverb type is set to (01)Hall1
        # This would be 01 00
        self._reverb = ReverbType.HALL1
        # Chorus type is set to (---)Chorus
        # I guess this would be 41 00
        self._chorus = ChorusType.CHORUS