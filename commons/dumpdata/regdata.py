import collections
import collections.abc

from ..util import CachedSequence
from ..exceptions import MalformedDataError
from ..values import BLANK, UnknownBytesValue
from .regvalues import DATA_SPECS


# you can't stop me
class RegData(CachedSequence):
    """
    Container for the useful data in a reg section
    """
    __slots__ = ('data')

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

        # more absolute silliness for no real gain

        def make_bank(idx, s=self.SETTING_SIZE, d=data[self.SETTINGS_SLICE]):
            return RegBank(idx+1, (d[idx*s:(idx+1)*s], d[(idx+8)*s:(idx+9)*s]))

        super().__init__(8, make_bank)

    def get_setting(self, bank, button):
        """Get the RegSetting object corresponding to the bank and button"""
        # data is stored by button, then banks
        # (i.e. all the settings for a button are together)
        # but it's more convenient to get and display as bank, then button
        if not 1 <= button <= 2:
            raise ValueError(f"Invalid button: {button}")
        if not 1 <= bank <= 8:
            raise ValueError(f"Invalid bank: {button}")
        return self[bank-1][button-1]

    def iter_settings(self):
        """Iterate through settings, grouped by bank then button"""
        for bank in self:
            yield from bank

    def _cereal(self):
        return [setting._cereal() for setting in self.iter_settings()]


class RegBank(CachedSequence):
    __slots__ = ('bank')

    def __init__(self, bank, setting_data):
        self.bank = bank

        def make_setting(idx, bank=bank, setting_data=setting_data):
            return RegSetting(bank, idx+1, setting_data[idx])

        super().__init__(len(setting_data), make_setting)


class RegSetting(collections.abc.Mapping):
    """
    Actual object that represents a registration memory setting
    Implements the Mapping abc.
    keys are the strings in regvalues.DATA_NAMES, which
    are supposed to be the names in the function menu
    Values are a namedtuple
    """
    SettingValue = collections.namedtuple(
        "SettingValue",
        "prop recorded value bytes unusual")

    def __init__(self, bank, button, data):

        self.bank = bank
        self.button = button

        self.data = data

        self._dict = dict.fromkeys(DATA_SPECS.SETTING_MAP.keys())
        self._unusual = []

        self._parse_values()

    # parse values
    def _parse_values(self):
        # We look ahead at the first byte:
        self.recorded = (self.data[0] != 0)
        for dname, (dslice, dfunc) in DATA_SPECS.SETTING_MAP.items():
            # get the data as byte slice:
            raw_bytes = self.data[dslice]
            # then interpret it:
            unusual = False
            if self.recorded:
                try:
                    value = dfunc(raw_bytes)
                except KeyError:
                    unusual = True
            else:
                if all(b == 0 for b in raw_bytes):
                    value = BLANK
                else:
                    unusual = True
            if unusual:
                value = UnknownBytesValue(raw_bytes)
            # we build the tuple...
            val = self.SettingValue(
                dname, self.recorded, value, raw_bytes, unusual)
            # then save it
            self._dict[dname] = val
            if unusual:
                self._note_unusual(val)
        # Do a check for the two split points
        if self.recorded and (self._dict["Split Point"].value
                              != self._dict["_Split Point 2"].value):
            self._note_unusual(self._dict["Split Point"])
            self._note_unusual(self._dict["_Split Point 2"])

    def _note_unusual(self, value):
        self._unusual.append(value)

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def print_settings(self):
        print(f"Bank {self.bank}, Button {self.button}:")
        for key, sval in self.iter_display_order_items():
            print(f" {key:>18}: {sval.value!s:>3}")

    def print_unusual(self):
        print(f" {len(self._unusual)} unusual values:")
        for sval in self._unusual:
            print(f" {sval.prop:>18}: {sval.value!s:>3}")

    def iter_display_order_items(self):
        """
        Iterator over the items, in DISPLAY_ORDER instead of storage order.
        This one is useful for printing out, because this order tries to
        match the order in the function menu / front panel screen.
        This doesn't iterate over all the keys, though as it excludes
        padding and the duplicate split point.
        """
        for key in DATA_SPECS.DISPLAY_ORDER:
            yield (key, self._dict[key])

    def unusual_len(self):
        return len(self._unusual)

    def unusual_iter(self):
        return iter(self._unusual)

    # cereal
    def _cereal(self):
        return collections.OrderedDict(
            (key, str(sval.value)) for key, sval in self.iter_display_order_items())
