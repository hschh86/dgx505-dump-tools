"""
collect.py

write out bulk dump data from a port or mido-text-file to a file
"""
# import sys
import argparse

from commons.util import eprint
from commons import mido_util, dgxdump

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
    'outfile', type=str,
    help="File to write to. Error if file already exists")

args = argparser.parse_args()

# DEALING WITH STDOUT IS A PAIN SO I'M NOT GONNA
#    if args.plaintext:
#        writeout = writeout_hex
#        if args.outfile is None:
#            outfile = sys.stdout
#        else:
#            outfile = open(args.outfile, 'xt')
#    else:
#        writeout = writeout_bytes
#        if args.outfile is None:
#            outfile = sys.stdout.buffer
#        else:
#            outfile = open(args.outfile, 'xb')
if args.plaintext:
    outfile = open(args.outfile, 'xt')
else:
    outfile = open(args.outfile, 'xb')


def _get_msgs(msgs):
    if args.all:
        messages = []
        for message in mido_util.grab_sysex_until_clock(msgs):
            eprint('Message recieved...')
            messages.append(message)
        eprint('Messages finished')
        return messages
    else:
        dump = dgxdump.DgxDump(msgs, verbose=True)
        return dump.iter_messages()


if args.file:
    with open(args.file, 'rt') as infile:
        eprint('Reading from file', args.file)
        messages = _get_msgs(mido_util.readin_strings(infile))
else:
    with mido_util.open_input(args.port,
                              args.guessport, args.virtual) as inport:
        eprint('Reading from port', inport.name)
        messages = _get_msgs(inport)

eprint('Writing file', args.outfile)
with outfile:
    if args.plaintext:
        eprint('Writing hex to', args.outfile)
        mido_util.writeout_hex(outfile, messages)
    else:
        eprint('writing bytes to', args.outfile)
        mido_util.writeout_bytes(outfile, messages)
eprint('Done!')
