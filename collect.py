"""
collect.py

write out bulk dump data from a port or mido-text-file to stdout
"""
import sys
import argparse

from commons import util, mido_util, dgxdump

argparser = argparse.ArgumentParser(
    description="Writes out bulk dump data to standard output")
argparser.add_argument(
    'input', type=str,
    help="Port to read from (run 'mido-ports' to list available ports)"
         " / Filename if applicable")

ingroup = argparser.add_argument_group("Input options")
inargs = ingroup.add_mutually_exclusive_group()
inargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
inargs.add_argument(
    '-V', '--virtual', action='store_true',
    help='Use virtual port')
inargs.add_argument(
    '-f', '--mfile', action='store_true',
    help="Read from mido message text file instead of port")


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


if args.mfile:
    with open(args.input, 'rt') as infile:
        sprint('Reading from file', args.input)
        messages = _get_msgs(mido_util.readin_strings(infile))
else:
    with mido_util.open_input(args.input,
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
