import collections
import struct
import functools

from .. import util
from ..maps import BytesAssertMap, RangeMap, KeyMap


@functools.lru_cache()  # cache it, because why not eh
def get_struct(bformat):
    return struct.Struct('>'+bformat)


# a 'useless class'
class _RegLookup(object):
    PAD_MAP = BytesAssertMap(b'\x00\x00')
    NUMBER_MAP = RangeMap()
    VOICE_MAP = RangeMap(1, 494, +1)
    OCTAVE_MAP = RangeMap(-2, +2, format_string="1d")
    SPLIT_MAP = KeyMap()
    REVERB_MAP = {
        1:  (1,    "01(Hall1)"),
        2:  (2,    "02(Hall2)"),
        3:  (3,    "03(Hall3)"),
        4:  (4,    "04(Room1)"),
        5:  (5,    "05(Room2)"),
        6:  (6,    "06(Stage1)"),
        7:  (7,    "07(Stage2)"),
        8:  (8,    "08(Plate1)"),
        9:  (9,    "09(Plate2)"),
        10: (10,   "10(Off)"),
        11: (None, "---(Room)"),
        12: (None, "---(Stage)"),
        13: (None, "---(Plate)"),
    }

    CHORUS_MAP = {
        1:  (1,    "01(Chorus1)"),
        2:  (2,    "02(Chorus2)"),
        3:  (3,    "03(Flanger1)"),
        4:  (4,    "04(Flanger2)"),
        5:  (5,    "05(Off)"),
        6:  (None, "---(Thru)"),
        7:  (None, "---(Chorus)"),
        8:  (None, "---(Celeste)"),
        9:  (None, "---(Flanger)"),
    }

    HARMONY_MAP = {
        1:  (1,  "01(Duet)"),
        2:  (2,  "02(Trio)"),
        3:  (3,  "03(Block)"),
        4:  (4,  "04(Country)"),
        5:  (5,  "05(Octave)"),
        6:  (6,  "06(Trill1/4)"),
        7:  (7,  "07(Trill1/6)"),
        8:  (8,  "08(Trill1/8)"),
        9:  (9,  "09(Trill1/12)"),
        10: (10, "10(Trill1/16)"),
        11: (11, "11(Trill1/24)"),
        12: (12, "12(Trill1/32)"),
        13: (13, "13(Tremolo1/4)"),
        14: (14, "14(Tremolo1/6)"),
        15: (15, "15(Tremolo1/8)"),
        16: (16, "16(Tremolo1/12)"),
        17: (17, "17(Tremolo1/16)"),
        18: (18, "18(Tremolo1/24)"),
        19: (19, "19(Tremolo1/32)"),
        20: (20, "20(Echo1/4)"),
        21: (21, "21(Echo1/6)"),
        22: (22, "22(Echo1/8)"),
        23: (23, "23(Echo1/12)"),
        24: (24, "24(Echo1/16)"),
        25: (25, "25(Echo1/24)"),
        26: (26, "26(Echo1/32)"),
    }

    BOOL_MAP = {
        0x00: (False, "OFF"),
        0x7F: (True,  "ON"),
    }

    SUSTAIN_MAP = {
        0x40: (False, "OFF"),
        0x6E: (True,  "ON"),
    }

    AB_MAP = {
        0xFF: (None, "---"),
        0x00: (0,    "Main A"),
        0x05: (5,    "Main B"),
    }

    ACMP_MAP = {
        0xFF: (None,  "---"),
        0x00: (False, "OFF"),
        0x01: (True,  "ON"),
    }

    SETTING_FORMATS = (
        # 00
        ("_first byte",         "1s",   BytesAssertMap(b'\x01')),
        # Style
        ("Style number",        "B",    RangeMap(1, 136, +1, 0xFF)),
        ("Accompaniment",       "B",    ACMP_MAP),
        ("Split Point",         "b",    SPLIT_MAP),
        ("_Split Point 2",      "b",    SPLIT_MAP),
        ("Main A/B",            "B",    AB_MAP),
        ("Style Volume",        "B",    RangeMap(none_val=0xFF)),
        # Main
        ("Main Voice number",   "H",    VOICE_MAP),
        ("M. Octave",           "b",    OCTAVE_MAP),
        ("M. Volume",           "b",    NUMBER_MAP),
        ("M. Pan",              "b",    NUMBER_MAP),
        ("M. Reverb Level",     "b",    NUMBER_MAP),
        ("M. Chorus Level",     "b",    NUMBER_MAP),
        # Split
        ("Split",               "b",    BOOL_MAP),
        ("Split Voice number",  "H",    VOICE_MAP),
        ("S. Octave",           "b",    OCTAVE_MAP),
        ("S. Volume",           "b",    NUMBER_MAP),
        ("S. Pan",              "b",    NUMBER_MAP),
        ("S. Reverb Level",     "b",    NUMBER_MAP),
        ("S. Chorus Level",     "b",    NUMBER_MAP),
        # Dual
        ("Dual",                "b",    BOOL_MAP),
        ("Dual Voice number",   "H",    VOICE_MAP),
        ("D. Octave",           "b",    OCTAVE_MAP),
        ("D. Volume",           "b",    NUMBER_MAP),
        ("D. Pan",              "b",    NUMBER_MAP),
        ("D. Reverb Level",     "b",    NUMBER_MAP),
        ("D. Chorus Level",     "b",    NUMBER_MAP),
        # Pitch, Reverb, Chorus
        ("Pitch Bend Range",    "b",    RangeMap(1, 12, format_string="02d")),
        ("Reverb Type",         "B",    REVERB_MAP),
        ("Chorus Type",         "B",    CHORUS_MAP),
        # Harmony
        ("Harmony",             "b",    BOOL_MAP),
        ("Harmony Type",        "B",    HARMONY_MAP),
        ("Harmony Volume",      "b",    NUMBER_MAP),
        # ff
        ("_ff byte",            "1s",   BytesAssertMap(b'\xFF')),
        # Transpose & Tempo
        ("Transpose",           "B",    RangeMap(-12, +12, -12, format_string="02d")),
        ("Tempo",               "B",    RangeMap(32, 280, +32, 0xFF, "3d")),
        # 00 00
        ("_pad 1",              "2s",   PAD_MAP),
        # Panel Sustain
        ("Sustain",             "B",    SUSTAIN_MAP),
        # 00 00
        ("_pad 2",              "2s",   PAD_MAP),
    )

    @staticmethod
    def make_bytemap_func(bstruct, mapping):
        struct_unpack = bstruct.unpack

        def bytemap_func(raw_bytes):
            (raw_value,) = struct_unpack(raw_bytes)
            return mapping[raw_value]

        return bytemap_func

    @util.lazy_property
    def SETTING_MAP(self):
        names, bformats, mappings = zip(*self.SETTING_FORMATS)
        bstructs = [get_struct(fmt) for fmt in bformats]
        dslices = util.cumulative_slices(s.size for s in bstructs)
        return collections.OrderedDict(
            (name, (dslice, self.make_bytemap_func(bstruct, mapping)))
            for (name, dslice, bstruct, mapping) in
            zip(names, dslices, bstructs, mappings))

    DISPLAY_ORDER = (
        # front panel
        "Style number",
        "Accompaniment",
        "Main A/B",
        "Tempo",
        "Main Voice number",
        "Dual Voice number",
        "Split Voice number",
        "Harmony",
        "Dual",
        "Split",
        # function menu
        "Style Volume",
        "Transpose",
        "Pitch Bend Range",
        "Split Point",
        "M. Volume",
        "M. Octave",
        "M. Pan",
        "M. Reverb Level",
        "M. Chorus Level",
        "D. Volume",
        "D. Octave",
        "D. Pan",
        "D. Reverb Level",
        "D. Chorus Level",
        "S. Volume",
        "S. Octave",
        "S. Pan",
        "S. Reverb Level",
        "S. Chorus Level",
        "Reverb Type",
        "Chorus Type",
        "Sustain",
        "Harmony Type",
        "Harmony Volume"
    )


DATA_SPECS = _RegLookup()
