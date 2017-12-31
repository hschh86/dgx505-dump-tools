import collections

from .dumpdata.messages import SongDumpSection, RegDumpSection
from .util import YAMAHA
from .mido_util import write_syx_file


def filter_yamaha_sysex(messages):
    return (m for m in messages if m.type == 'sysex' and m.data[0] == YAMAHA)


class DgxDump(object):
    # Object-Orientation?
    # More Abstractions, More Often!

    def __init__(self, messages, verbose=False, song=True, reg=True):

        self._sections = []
        stream = filter_yamaha_sysex(messages)
        # could be improved...

        if song:
            self.song_data = SongDumpSection(stream, verbose)
            self._sections.append(self.song_data)
        else:
            self.song_data = None

        if reg:
            self.reg_data = RegDumpSection(stream, verbose)
            self._sections.append(self.reg_data)
        else:
            self.reg_data = None

    def iter_messages(self):
        for section in self._sections:
            yield from section.iter_messages()

    def write_syx(self, outfile):
        write_syx_file(outfile, self.iter_messages())

    def _cereal(self):
        return collections.OrderedDict([
            ('song_data',
             self.song_data._cereal() if self.song_data else None),
            ('reg_data',
             self.reg_data._cereal() if self.reg_data else None)
        ])
