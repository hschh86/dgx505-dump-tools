import argparse
import logging

from commons import mido_util, dgxdump, exceptions


class UserSongNumberListAction(argparse.Action):
    """
    argparse action for unique list of user song numbers (1-5).
    argparse.ArgumentError raised for invalid or duplicate song numbers.
    If option invoked without arguments, [1, 2, 3, 4, 5] is set.
    """
    def __init__(self, option_strings, dest, **kwargs):
        kwargs['nargs'] = '*'
        kwargs['type'] = int
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        SONGS = range(1, 5+1)
        if values is None:
            setattr(namespace, self.dest, self.default)
        elif values == []:
            setattr(namespace, self.dest, list(SONGS))
        else:
            seen = set()
            for value in values:
                if value not in SONGS:
                    raise argparse.ArgumentError(
                        self, "Invalid song number: {}".format(value))
                if value in seen:
                    raise argparse.ArgumentError(
                        self, "Duplicate song number: {}".format(value))
                seen.add(value)
            setattr(namespace, self.dest, values)


class EnsureSingleFormatAction(argparse.Action):
    """
    Argparse action for the filename pattern.
    Should receive a format string with one argument for the song number
    Tests for validity by attempting to format with 1 and 2
    """

    def __call__(self, parser, namespace, values, option_string=None):
        # try out some formats
        try:
            invalid = (str.format(values, 1) == str.format(values, 2))
        except (IndexError, ValueError):
            invalid = True
        if invalid:
            raise argparse.ArgumentError(
                self, "Invalid format: {!r}".format(values))
        else:
            setattr(namespace, self.dest, values)


class RegBankButtonListAction(argparse.Action):
    """
    Argparse action for list of unique regist identifiers, which are
    the bank then button numbers joined with comma.
    Single numbers are used as shorthand for both settings in a the bank,
    for example "2" expands to "2,1 2,2"
    """
    def __init__(self, option_strings, dest, **kwargs):
        kwargs['nargs'] = '*'
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # A list of regist identifiers, where regist identifier
        # are either a number [1-8], representing a bank, or
        # a pair of numbers with a comma [1-8],[1-2] representing bank+button.
        # duplicate entries, inc. bank only, error.

        # values = a list, or None
        BANKS = range(1, 8+1)
        BUTTONS = range(1, 2+1)
        if values is None:
            setattr(namespace, self.dest, self.default)
        else:
            # assume values is a list of strings.
            value_list = []
            seen = set()

            def addident(bank, button):
                if bank not in BANKS:
                    raise argparse.ArgumentError(
                        self, "Invalid bank {},{}".format(bank, button))
                if button not in BUTTONS:
                    raise argparse.ArgumentError(
                        self, "Invalid button {},{}".format(bank, button))
                bt = (bank, button)
                if bt in seen:
                    raise argparse.ArgumentError(
                        self,
                        "Duplicate identifier {},{}".format(bank, button))
                seen.add(bt)
                value_list.append(bt)

            for value in values:
                try:
                    x = int(value)
                except ValueError:
                    try:
                        x, y = map(int, value.split(","))
                    except (IndexError, ValueError):
                        raise argparse.ArgumentError(
                            self, "Invalid argument {!r}".format(value))
                    addident(x, y)
                else:
                    addident(x, 1)
                    addident(x, 2)

            setattr(namespace, self.dest, value_list)


# argparser stuff
argparser = argparse.ArgumentParser(
    description="Extract UserSong MIDI files from a sysex dump")
argparser.add_argument(
    'file', type=str,
    help="File to read from")

ingroup = argparser.add_argument_group("Input options")
ingroup.add_argument(
    '--mfile', action='store_true',
    help="Read from mido message text file instead of syx file")

printgroup = argparser.add_argument_group("Text output (stdout)")
printgroup.add_argument(
    '-S', '--printsong', metavar='N',
    action=UserSongNumberListAction,
    help="Print out information for these user songs")
printgroup.add_argument(
    '-R', '--printreg', metavar='X',
    action=RegBankButtonListAction,
    help="Print out information for these regist settings")

midigroup = argparser.add_argument_group("MIDI File output")
midigroup.add_argument(
    '-s', '--writesong', metavar='N',
    action=UserSongNumberListAction,
    help="Write out midi files for these user songs")
midigroup.add_argument(
    '-n', '--nameformat', type=str, metavar='FORMAT',
    default='UserSong{:1d}.mid', action=EnsureSingleFormatAction,
    help="Python-format string for output midi file")
midigroup.add_argument(
    '-c', '--clobber', action='store_true',
    help='overwrite files that already exist (skips by default)')

argparser.add_argument(
    '-v', '--verbose', action='count', default=0,
    help="Verbose messages. -v for basic, -vv for file parsing messages")


def _read_dump_from_filename(filename, mfile=False, log=__name__, sublog=None):
        with mido_util.read_messages_file(filename, mfile, log) as messages:
            dump = dgxdump.DgxDump(messages, log=sublog)
        return dump


if __name__ == '__main__':
    # args
    args = argparser.parse_args()
    if all(x is None for x in (args.writesong, args.printsong, args.printreg)):
        argparser.error("at least one of -S -R -s is required (no output)")

    # logger
    logger = logging.getLogger('extractor')
    read_logger = logging.getLogger('extractor.read')
    logger_handler = logging.StreamHandler()
    logger.addHandler(logger_handler)

    if args.verbose > 0:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
    if args.verbose > 1:
        read_logger.setLevel(logging.INFO)
    else:
        read_logger.setLevel(logging.WARNING)

    # CLOBBER
    if args.clobber:
        fmode = 'wb'
    else:
        fmode = 'xb'

    # INPUT
    dump = _read_dump_from_filename(args.file, args.mfile,
                                    log='extractor', sublog='extractor.read')

    # Printing to stdout.
    if args.printsong is not None:
        logger.info('Printing song info to stdout')
        songs = dump.song_data.songs
        for song_number in args.printsong:
            songs.get_song(song_number).print_info()
            print()
    if args.printreg is not None:
        logger.info('Printing reg info to stdout')
        reg_settings = dump.reg_data.settings
        if args.printreg == []:
            settings = reg_settings.iter_settings()
        else:
            settings = (reg_settings.get_setting(*i) for i in args.printreg)
        for setting in settings:
            setting.print_settings()
            print()

    # Writing out songs:
    if args.writesong is not None:
        logger.info('Writing User Song midi files.')
        for song_number in args.writesong:
            song = dump.song_data.songs.get_song(song_number)
            try:
                midi = song.midi
            except exceptions.NotRecordedError:
                logger.info("User Song %d - not recorded.", song_number)
            else:
                filename = args.nameformat.format(song_number)
                logger.info("User Song %d - Writing midi file %r",
                            song_number, filename)
                try:
                    with open(filename, fmode) as outfile:
                        outfile.write(midi)
                except FileExistsError:
                    logger.warning("Error: file %r exists. Ignoring.",
                                   filename)
