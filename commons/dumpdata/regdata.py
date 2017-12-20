import collections

from ..util import lazy_property
from ..exceptions import MalformedDataError
from .messages import DumpSection
from .regvalues import (DATA_NAMES, DATA_SLICE_DICT, DATA_STRUCT_DICT,
                        DATA_MAP_DICT, DISPLAY_ORDER)


class RegDumpSection(DumpSection):
    """
    The reg section of the dump
    """
    SECTION_BYTE = 0x09
    SECTION_NAME = "Registration data"
    EXPECTED_COUNT = 2
    EXPECTED_RUN = 816

    @lazy_property
    def settings(self):
        return RegData(self.data)

    def _cereal(self):
        return self.settings._cereal()


# you can't stop me
class RegData(object):
    """
    Container for the useful data in a reg section
    """

    START_SLICE = slice(0x000, 0x004)
    SETTINGS_SLICE = slice(0x004, 0x2C4)
    END_SLICE = slice(0x2C4, 0x2C8)

    EXPECTED_SIZE = 0x2C8
    SETTING_SIZE = 0x2C

    BOOKEND = b'PSR\x03'

    def _message_format_checks(self):
        if len(self.data) != self.EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        if not (self.data[self.START_SLICE]
                == self.data[self.END_SLICE] == self.BOOKEND):
            raise MalformedDataError("Invalid format")

    def __init__(self, data):

        self.data = data
        self._message_format_checks()
        self._setting_data = data[self.SETTINGS_SLICE]

        self._settings = [None] * 16

    @staticmethod
    def _bankbtn_to_idx(bank, button):
        # data is stored by button, then bank
        # (i.e. all the settings for a button are together)
        # but it's more convenient to get and display as bank, then button
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        return (button-1)*8 + (bank-1)

    def get_setting(self, bank, button):
        """Get the RegSetting object corresponding to the bank and button"""
        idx = self._bankbtn_to_idx(bank, button)
        reg = self._settings[idx]
        if reg is None:
            slc = slice(idx*self.SETTING_SIZE, (idx+1)*self.SETTING_SIZE)
            set_section = self._setting_data[slc]
            reg = RegSetting(bank, button, set_section)
            self._settings[idx] = reg
        return reg

    def __iter__(self):
        """Iterate through settings, grouped by bank then button"""
        for bank in range(1, 8+1):
            for button in range(1, 2+1):
                yield self.get_setting(bank, button)

    def _cereal(self):
        return [setting._cereal() for setting in self]


SettingValue = collections.namedtuple("SettingValue",
                                      "prop value vstr bytes unusual")


class RegSetting(object):

    def __init__(self, bank, button, data):

        self.bank = bank
        self.button = button

        self.data = data

        self._dict = dict.fromkeys(DATA_NAMES)
        self._unusual = []

        self._parse_values()

        # parse values
    def _parse_values(self):
        for key in DATA_NAMES:
            # get the data as byte slice:
            raw_bytes = self.data[DATA_SLICE_DICT[key]]
            # then unpack it:
            (raw_value,) = DATA_STRUCT_DICT[key].unpack(raw_bytes)
            # then interpret it:
            key_mapping = DATA_MAP_DICT[key]
            try:
                value, vstr = key_mapping[raw_value]
                unusual = False
            except KeyError:
                value = raw_bytes
                vstr = '<unknown {}>'.format(raw_bytes.hex())
                unusual = True
            # we build the tuple...
            val = SettingValue(key, value, vstr, raw_bytes, unusual)
            # then save it
            self._dict[key] = val
            if unusual:
                self._note_unusual(val)

    def _note_unusual(self, value):
        self._unusual.append(value)

    def __getitem__(self, key):
        return self._dict[key]

    def print_settings(self):
        print("Bank {}, Button {}:".format(self.bank, self.button))
        for key, sval in self.iter_display_order_items():
            print(" {:>18}: {:>3}".format(key, sval.vstr))

    def print_unusual(self):
        print(" {} unusual values:".format(len(self._unusual)))
        for sval in self._unusual:
            print(" {:>18}: {:>3}".format(sval.prop, sval.vstr))

    def iter_display_order_items(self):
        for key in DISPLAY_ORDER:
            yield (key, self._dict[key])

    def unusual_len(self):
        return len(self._unusual)

    def unusual_iter(self):
        return iter(self._unusual)

    def __iter__(self):
        return iter(DATA_NAMES)

    def __len__(self):
        return len(DATA_NAMES)

    def __contains__(self, item):
        return item in DATA_NAMES

    # cereal
    def _cereal(self):
        return collections.OrderedDict(
            (key, sval.vstr) for key, sval in self.iter_display_order_items())
