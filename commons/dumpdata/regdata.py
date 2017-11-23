import collections
import struct

from ..util import slicebyn
from ..exceptions import MalformedDataError
from .messages import DataSection


class RegData(DataSection):
    """
    Container for the useful data in a reg section
    """
    SECTION_BYTE = 0x09
    SECTION_NAME = "Registration data"
    EXPECTED_COUNT = 2
    EXPECTED_RUN = 816

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        START_SLICE = slice(0x000, 0x004)
        SETTINGS_SLICE = slice(0x004, 0x2C4)
        END_SLICE = slice(0x2C4, 0x2C8)
        PAD_SLICE = slice(0x2C8, None)

        EXPECTED_SIZE = 0x2CA
        SETTING_SIZE = 0x2C

        BOOKEND = b'PSR\x03'
        PADBYTES = b'\x00\x00'

        # message format checks
        if len(self.data) != EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        if not ((self.data[START_SLICE] == self.data[END_SLICE] == BOOKEND)
                and (self.data[PAD_SLICE] == PADBYTES)):
            raise MalformedDataError("Invalid format")

        # data is stored by button, then bank
        # (i.e. all the settings for a button are together)
        button_list = []
        button_sections = slicebyn(self.data[SETTINGS_SLICE], SETTING_SIZE*8)
        for button_num, button_section in zip(range(1, 2+1), button_sections):
            bank_list = []
            set_sections = slicebyn(button_section, SETTING_SIZE)
            for bank_num, set_section in zip(range(1, 8+1), set_sections):
                reg = RegSetting(bank_num, button_num, set_section)
                bank_list.append(reg)
            button_list.append(bank_list)
        # it's more convenient to store and display as bank, then button
        self.settings = tuple(zip(*button_list))

    def get_settings(self, bank, button):
        """Get the RegSetting object corresponding to the bank and button"""
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        return self.settings[bank-1][button-1]

    def __iter__(self):
        """Iterate through settings, grouped by bank then button"""
        for bank in self.settings:
            yield from bank

    def _cereal(self):
        return [setting._cereal() for setting in self]


class RegSetting(collections.abc.Mapping):

    REVERB_MAP = {
        1:  "01 Hall1",
        2:  "02 Hall2",
        3:  "03 Hall3",
        4:  "04 Room1",
        5:  "05 Room2",
        6:  "06 Stage1",
        7:  "07 Stage2",
        8:  "08 Plate1",
        9:  "09 Plate2",
        10: "10 Off",
        11: "-- Room",
        12: "-- Stage",
        13: "-- Plate"
    }

    CHORUS_MAP = {
         1: "01 Chorus1",
         2: "02 Chorus2",
         3: "03 Flanger1",
         4: "04 Flanger2",
         5: "05 Off",
         6: "-- Thru",
         7: "-- Chorus",
         8: "-- Celeste",
         9: "-- Flanger"
    }

    HARMONY_MAP = {
        1:  "01 Duet",
        2:  "02 Trio",
        3:  "03 Block",
        4:  "04 Country",
        5:  "05 Octave",
        6:  "06 Trill 1/4",
        7:  "07 Trill 1/6",
        8:  "08 Trill 1/8",
        9:  "09 Trill 1/12",
        10: "10 Trill 1/16",
        11: "11 Trill 1/24",
        12: "12 Trill 1/32",
        13: "13 Tremolo 1/4",
        14: "14 Tremolo 1/6",
        15: "15 Tremolo 1/8",
        16: "16 Tremolo 1/12",
        17: "17 Tremolo 1/16",
        18: "18 Tremolo 1/24",
        19: "19 Tremolo 1/32",
        20: "20 Echo 1/4",
        21: "21 Echo 1/6",
        22: "22 Echo 1/8",
        23: "23 Echo 1/12",
        24: "24 Echo 1/16",
        25: "25 Echo 1/24",
        26: "26 Echo 1/32"
    }

    BOOL_MAP = {
        0x00: "OFF",
        0x7F: "ON"
    }

    SUSTAIN_MAP = {
        0x40: "OFF",
        0x6E: "ON"
    }

    AB_MAP = {
        0xFF: None,
        0x00: "Main A",
        0x05: "Main B"
    }

    ACMP_MAP = {
        0xFF: None,
        0x00: "OFF",
        0x01: "ON"
    }

    REG_SETTING_FORMATS = collections.OrderedDict([
        # front panel
        ("Style number", "03d"),
        ("Accompaniment", "s"),
        ("Main A/B", "s"),
        ("Tempo", "3d"),

        ("Main Voice number", "03d"),
        ("Dual Voice number", "03d"),
        ("Split Voice number", "03d"),

        ("Harmony", "s"),
        ("Dual", "s"),
        ("Split", "s"),

        # function menu
        ("Style Volume", "03d"),
        ("Transpose", "02d"),
        ("Pitch Bend Range", "02d"),
        ("Split Point", "03d"),

        ("M. Volume", "03d"),
        ("M. Octave", "1d"),
        ("M. Pan", "03d"),
        ("M. Reverb Level", "03d"),
        ("M. Chorus Level", "03d"),

        ("D. Volume", "03d"),
        ("D. Octave", "1d"),
        ("D. Pan", "03d"),
        ("D. Reverb Level", "03d"),
        ("D. Chorus Level", "03d"),

        ("S. Volume", "03d"),
        ("S. Octave", "1d"),
        ("S. Pan", "03d"),
        ("S. Reverb Level", "03d"),
        ("S. Chorus Level", "03d"),

        ("Reverb Type", "s"),
        ("Chorus Type", "s"),
        ("Sustain", "s"),

        ("Harmony Type", "s"),
        ("Harmony Volume", "03d")
    ])

    REG_SETTING_NAMES = REG_SETTING_FORMATS.keys()

    SFORMAT = '> B BBbbBB Hbbbbb bHbbbbb bHbbbbb bBB bBb B BB 2s B 2s'

    SettingValue = collections.namedtuple("SettingValue", "value raw unusual")

    def __init__(self, bank, button, data):

        self.bank = bank
        self.button = button

        self._dict = collections.OrderedDict(
            (x, None) for x in self.REG_SETTING_NAMES)
        self._unusual = []

        self._parse_data(data)

    def _note_unusual(self, message):
        # Do something with the message, like put it in a list
        self._unusual.append(message)

    def _range_check_assign(self, prop, raw,
                            lo=0, hi=127, offset=0, noneval=None):
        """
        Assign a value to a property, checking if value falls within range
        If value doesn't, _note_unusual will be called, and the 'unusual'
        field will have a message (instead of None).
        prop = property name
        raw = raw value (stored in raw field of the SettingValue tuple)
        lo = lower bound (inclusive)
        hi = upper bound (inclusive)
        offset = value to add to raw before range check
        noneval = if raw == noneval, value becomes None. (check is skipped)

        self._dict[prop] is assigned a SettingValue(value, raw, unusual) tuple
        """
        unusual = None
        if raw == noneval:
            value = None
        else:
            value = raw + offset
            if not (lo <= value <= hi):
                unusual = "{} out of range: {}".format(prop, value)
                self._note_unusual(unusual)
        self._dict[prop] = self.SettingValue(value, raw, unusual)

    def _mapping_check_assign(self, prop, raw, mapping):
        """
        Assign a value to a property, where value is mapping[raw]
        If mapping doesn't have key, _note_unusual will be called,
        and the 'unusual' field will have a message (instead of None).

        self._dict[prop] is assigned a SettingValue(value, raw, unusual) tuple
        """
        unusual = None
        try:
            value = mapping[raw]
        except KeyError:
            value = raw
            unusual = "{} unusual value: {}".format(value)
            self._note_unusual(unusual)
        self._dict[prop] = self.SettingValue(value, raw, unusual)

    def _parse_data(self, data):
        """
        Parse the data into self._dict and self._unusual.
        Does checks, but messages are put into self._unusual instead of
        raised as exceptions.
        """
        (firstbyte,
         style_num, style_acmp, spoint1, spoint2, style_ab, style_vol,
         main_num, main_oct, main_vol, main_pan, main_rvb, main_chs,
         split_on,
         split_num, split_oct, split_vol, split_pan, split_rvb, split_chs,
         dual_on,
         dual_num, dual_oct, dual_vol, dual_pan, dual_rvb, dual_chs,
         pbend, rvb_type, chs_type,
         hmny_on, hmny_type, hmny_vol,
         ffbyte,
         tspose, tempo,
         pad1,
         psust,
         pad2) = struct.unpack(self.SFORMAT, data)

        if firstbyte != 0x01:
            self._note_unusual('firstbyte is {:02X}'.format(firstbyte))
        if ffbyte != 0xFF:
            self._note_unusual('ffbyte is {:02X}'.format(ffbyte))
        if not (pad1 == pad2 == b'\x00\x00'):
            self._note_unusual('padding is {!r} {!r}'.format(pad1, pad2))

        # Style front panel buttons
        self._range_check_assign('Style number', style_num, 1, 136,
                                 offset=+1, noneval=0xFF)

        self._mapping_check_assign('Accompaniment', style_acmp, self.ACMP_MAP)
        self._mapping_check_assign('Main A/B', style_ab, self.AB_MAP)

        self._range_check_assign('Tempo', tempo, 32, 280,
                                 offset=+32, noneval=0xFF)

        # Voice numbers
        self._range_check_assign('Main Voice number', main_num, 1, 494,
                                 offset=+1)
        self._range_check_assign('Split Voice number', split_num, 1, 494,
                                 offset=+1)
        self._range_check_assign('Dual Voice number', dual_num, 1, 494,
                                 offset=+1)

        # Voice front panel buttons
        self._mapping_check_assign('Harmony', hmny_on, self.BOOL_MAP)
        self._mapping_check_assign('Dual', dual_on, self.BOOL_MAP)
        self._mapping_check_assign('Split', split_on, self.BOOL_MAP)

        # Function Menu
        self._range_check_assign('Style Volume', style_vol, noneval=0xFF)

        self._range_check_assign('Transpose', tspose, -12, +12, offset=-12)
        self._range_check_assign('Pitch Bend Range', pbend, 1, 12)

        if spoint1 != spoint2:
            self._note_unusual(
                "Split points don't match: 0x{:02X}, 0x{:02X}".format(
                    spoint1, spoint2))
        self._range_check_assign('Split Point', spoint1)

        # Main Voice
        self._range_check_assign('M. Volume', main_vol)
        self._range_check_assign('M. Octave', main_oct, -2, +2)
        self._range_check_assign('M. Pan', main_pan)
        self._range_check_assign('M. Reverb Level', main_rvb)
        self._range_check_assign('M. Chorus Level', main_chs)

        # Dual Voice
        self._range_check_assign('D. Volume', dual_vol)
        self._range_check_assign('D. Octave', dual_oct, -2, +2)
        self._range_check_assign('D. Pan', dual_pan)
        self._range_check_assign('D. Reverb Level', dual_rvb)
        self._range_check_assign('D. Chorus Level', dual_chs)

        # Split Voice
        self._range_check_assign('S. Volume', split_vol)
        self._range_check_assign('S. Octave', split_oct, -2, +2)
        self._range_check_assign('S. Pan', split_pan)
        self._range_check_assign('S. Reverb Level', split_rvb)
        self._range_check_assign('S. Chorus Level', split_chs)

        # Effects
        self._mapping_check_assign('Reverb Type', rvb_type, self.REVERB_MAP)
        self._mapping_check_assign('Chorus Type', chs_type, self.CHORUS_MAP)
        self._mapping_check_assign('Sustain', psust, self.SUSTAIN_MAP)

        # Harmony
        self._mapping_check_assign('Harmony Type', hmny_type, self.HARMONY_MAP)
        self._range_check_assign('Harmony Volume', hmny_vol)

    def print_settings(self):
        print("Bank {}, Button {}:".format(self.bank, self.button))
        for key, (value, raw, unusual) in self._dict.items():
            try:
                rep = format(value, self.REG_SETTING_FORMATS[key])
            except (TypeError, ValueError):
                rep = str(value)
            print(" {:>18}: {:>3}".format(key, rep))
        if self._unusual:
            print(" {} unusual values:".format(len(self._unusual)))
            for message in self._unusual:
                print(" - {}".format(message))

    # Methods required for Mapping abc: use underlying self._dict
    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    # cereal
    def _cereal(self):
        return collections.OrderedDict(
            (key, value.value) for key, value in self._dict.items())
