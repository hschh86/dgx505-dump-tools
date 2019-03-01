import collections
import struct
import functools

from .. import util
from ..maps import BytesAssertMap, RangeMap, EffectTypeMap, KeyMap
from ..values import (HarmonyType, ReverbType, ChorusType,
    AcmpSection, BLANK, SwitchBool)


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
    REVERB_MAP = EffectTypeMap(ReverbType)
    CHORUS_MAP = EffectTypeMap(ChorusType)
    HARMONY_MAP = EffectTypeMap(HarmonyType)

    BOOL_MAP = {
        0x00: SwitchBool.OFF,
        0x7F: SwitchBool.ON,
    }

    SUSTAIN_MAP = {
        0x40: SwitchBool.OFF,
        0x6E: SwitchBool.ON,
    }

    AB_MAP = {
        0xFF: BLANK,
        0x00: AcmpSection.MAIN_A,
        0x05: AcmpSection.MAIN_B,
    }

    ACMP_MAP = {
        0xFF: BLANK,
        0x00: SwitchBool.OFF,
        0x01: SwitchBool.ON,
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
        ("Tempo",               "B",    RangeMap(32, 280, +32, 0xFF)),
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
