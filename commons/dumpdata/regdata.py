import collections

from ..util import slicebyn, lazy_readonly_property
from ..exceptions import MalformedDataError
from .messages import DumpSection
from .regvalues import (DATA_NAMES, DATA_SLICE_DICT, DATA_STRUCT_DICT,
                        DATA_MAP_DICT, DISPLAY_ORDER)


class RegDumpSection(DumpSection):
    """
    Container for the useful data in a reg section
    """
    SECTION_BYTE = 0x09
    SECTION_NAME = "Registration data"
    EXPECTED_COUNT = 2
    EXPECTED_RUN = 816

    @lazy_readonly_property
    def settings(self):
        return RegData(self.data)

    def _cereal(self):
        return self.settings._cereal()


# you can't stop me
class RegData(object):

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


        button_list = []
        button_sections = slicebyn(self.data[self.SETTINGS_SLICE],
                                   self.SETTING_SIZE*8)
        for button_num, button_section in zip(range(1, 2+1), button_sections):
            bank_list = []
            set_sections = slicebyn(button_section, self.SETTING_SIZE)
            for bank_num, set_section in zip(range(1, 8+1), set_sections):
                reg = RegSetting(bank_num, button_num, set_section)
                bank_list.append(reg)
            button_list.append(bank_list)
        # it's more convenient to store and display as bank, then button
        self._settings = tuple(zip(*button_list))

    def _regsectiondata(self, bank, button):
        # data is stored by button, then bank
        # (i.e. all the settings for a button are together)
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        return self._setting_data[s]
        return

    def get_setting(self, bank, button):
        """Get the RegSetting object corresponding to the bank and button"""
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        return self._settings[bank-1][button-1]

    def __iter__(self):
        """Iterate through settings, grouped by bank then button"""
        for bank in self._settings:
            yield from bank

    def _cereal(self):
        return [setting._cereal() for setting in self]


SettingValue = collections.namedtuple("SettingValue",
                                      "prop value vstr bytes unusual")

class RegSetting(collections.abc.Mapping):

    def __init__(self, bank, button, data):

        self.bank = bank
        self.button = button

        self.data = data

        self._dict = dict.fromkeys(DATA_NAMES)

    def __getitem__(self, key):
        # first, look in the dict to see if we have it already
        val = self._dict[key]
        # invalid data names will raise KeyError here
        if val is not None:
            return val
        # We don't have it, so we'll have to make the item.
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
        # then save it and return.
        self._dict[key] = val
        return val

    def print_settings(self):
        print("Bank {}, Button {}:".format(self.bank, self.button))
        for key, sval in self.iter_display_order_items():
            print(" {:>18}: {:>3}".format(key, sval.vstr))

    def print_unusual(self):
        print(" {} unusual values:".format(len(self._unusual)))
        for message in self._unusual:
            print(" - {}".format(message))

    def iter_display_order_items(self):
        for key in DISPLAY_ORDER:
            yield (key, self[key])

    @lazy_readonly_property
    def unusual(self):
        # iterate over all the settings and see which are Unusual.
        # This will generate all the SettingValue objects:
        return tuple(sval for sval in self.values() if sval.unusual)

    def __iter__(self):
        # should I use DATA_NAMES or DISPLAY_ORDER for this?
        # Does it matter for the mixin?
        return iter(DATA_NAMES)

    def __len__(self):
        return len(DATA_NAMES)

    # I'm not sure if this is the way you're supposed to do this...
    def __eq__(self, other):
        if not isinstance(other, RegSetting):
            return NotImplemented
        return self.data == other.data

    def __hash__(self):
        return hash(self.data)

    # cereal
    def _cereal(self):
        return collections.OrderedDict(
            (key, sval.vstr) for key, sval in self.iter_display_order_items())
