import argparse

import mido

from commons.util import eprint
from commons.mido_util import read_syx_file
from commons.dgxdump import DgxDump
from commons.exceptions import NotRecordedError


def _read_dump_from_filename(filename, verbose=False):
    # if filename == '-':
    #     # stdin in binary mode
    #     # Needs EOF.
    #     if args.verbose:
    #         eprint("Reading from stdin")
    #     messages = read_syx_file(sys.stdin.buffer)
    # else:
    if verbose:
        eprint("Reading from file {!r}".format(filename))
    with open(filename, 'rb') as infile:
        messages = read_syx_file(infile)
    if verbose:
        eprint("All messages read from file")
    return DgxDump(messages, verbose)


def _read_dump_from_portname(portname, verbose=False):
    with mido.open_input(portname) as inport:
        if verbose:
            eprint("Listening to port {!r}".format(inport.name))
        dump = DgxDump(inport, verbose)
        if verbose:
            eprint("All messages read from port")
    return dump


# argparser stuff
_argparser = argparse.ArgumentParser(
    description="Extract UserSong MIDI files from a sysex dump")
_argparser.add_argument(
    'input', type=str,
    help="Port to read from (run 'mido-ports' to list available ports)"
         " / Filename")

_ingroup = _argparser.add_argument_group("Input options")
_ingroup.add_argument(
    '-f', '--fileinput', action='store_true',
    help="Read from file instead of port")

_outgroup = _argparser.add_argument_group("Output options")
_outgroup.add_argument(
    '-m', '--midiprefix', type=str,
    help="write out usersong midi with this file prefix")
_outgroup.add_argument(
    '-d', '--dumpfile', type=str,
    help="write out syx dump with this filename"),
_outgroup.add_argument(
    '-c', '--clobber', action='store_true',
    help='overwrite files that already exist')

_rgroup = _argparser.add_argument_group("Other options")
_rgroup.add_argument(
    '-v', '--verbose', action='store_true',
    help='Print progress messages to stderr')
_rgroup.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print the song stats and one-touch-settings to stdout")


def _main(args):
    if args.fileinput:
        dump = _read_dump_from_filename(
            args.input, args.verbose)
    else:
        dump = _read_dump_from_portname(
            args.input, args.verbose)

    if args.clobber:
        fmode = 'wb'
    else:
        fmode = 'xb'

    if args.dumpfile is not None:
        if args.verbose:
            eprint("Writing dump file {!r}".format(args.dumpfile))
        try:
            with open(args.dumpfile, fmode) as outfile:
                dump.write_syx(outfile)
        except FileExistsError:
            eprint("Error: file exists: {!r}. Ignoring...".format(
                args.dumpfile))

    for song in dump.song_data.songs:
        if not args.quiet:
            song.print_info()
            print()
        if args.midiprefix is not None:
            try:
                midi = song.midi
            except NotRecordedError:
                pass
            else:
                filename = "{}_UserSong{}.mid".format(
                    args.midiprefix, song.number)
                if args.verbose:
                    eprint("Writing midi file {!r}".format(filename))
                try:
                    with open(filename, fmode) as outfile:
                        outfile.write(midi)
                except FileExistsError:
                    eprint("Error: file exists: {!r}. Ignoring...".format(
                        filename))

    if not args.quiet:
        for setting in dump.reg_data:
            setting.print_settings()
            print()


if __name__ == "__main__":
    args = _argparser.parse_args()
    _main(args)
