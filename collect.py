"""
collect.py

write out bulk dump data from a port or mido-text-file to stdout
"""
import sys
import argparse

from commons import util, mido_util, dgxdump

argparser = argparse.ArgumentParser(
    description="Writes out bulk dump data to file")

inargs = argparser.add_mutually_exclusive_group()
inargs.add_argument(
    '-p', '--port', type=str,
    help="Port to read from (run 'mido-ports' to list available ports)")
inargs.add_argument(
    '-f', '--file', type=str,
    help="Text mido message file to read from")

portargs = argparser.add_mutually_exclusive_group()
portargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
portargs.add_argument(
    '-v', '--virtual', action='store_true',
    help='Use virtual port')

argparser.add_argument(
    '-a', '--all', action='store_true',
    help="Grab all the sysex messages until clock, no checks")

argparser.add_argument(
    '-t', '--plaintext', action='store_true',
    help="Write as hexadecimal text instead of binary")

argparser.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print progress messages to stderr")

# argparser.add_argument(
#     'outfile', type=str,
#     help="File to write to. Error if file already exists")

args = argparser.parse_args()


# if args.plaintext:
#     outfile = open(args.outfile, 'xt')
# else:
#     outfile = open(args.outfile, 'xb')

if args.quiet:
    sprint = util.nop
else:
    sprint = util.eprint


def _get_msgs(msgs):
    if args.all:
        messages = []
        for message in mido_util.grab_sysex_until_clock(msgs):
            sprint('Message received...')
            messages.append(message)
        sprint('Messages finished')
        return messages
    else:
        dump = dgxdump.DgxDump(msgs, verbose=not args.quiet)
        return dump.iter_messages()


if args.file:
    with open(args.file, 'rt') as infile:
        sprint('Reading from file', args.file)
        messages = _get_msgs(mido_util.readin_strings(infile))
else:
    with mido_util.open_input(args.port,
                              args.guessport, args.virtual) as inport:
        sprint('Reading from port', inport.name)
        messages = _get_msgs(inport)

# eprint('Writing file', args.outfile)

if args.plaintext:
    sprint('Writing hex to stdout')
    mido_util.writeout_hex(sys.stdout, messages)
else:
    sprint('writing bytes to stdout')
    mido_util.writeout_bytes(sys.stdout.buffer, messages)

sprint('Done!')
