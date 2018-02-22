"""
collect.py

write out bulk dump data from a port or mido-text-file to stdout
"""
import sys
import argparse
import logging
import io

from commons import mido_util, dgxdump

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
inargs.add_argument(
    '--sfile', action='store_true',
    help="Read from syx file instead of port")


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

# set up logger
logger = logging.getLogger('collect')
handler = logging.StreamHandler()
logger.addHandler(handler)
if args.quiet:
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.INFO)


def _get_msgs(msgs):
    if args.all:
        messages = []
        for message in mido_util.grab_sysex_until_clock(msgs):
            logger.info('Message received...')
            messages.append(message)
        logger.info('Messages finished')
        return messages
    else:
        dump = dgxdump.DgxDump(msgs, log='collect')
        return dump.iter_messages()


# I should probably refactor this with the one in extractor.py
if args.mfile:
    with open(args.input, 'rt') as infile:
        logger.info('Reading from midotext file %r', args.input)
        messages = _get_msgs(mido_util.readin_strings(infile))
elif args.sfile:
    with open(args.input, 'rb') as infile:
        logger.info('Reading from syx file %r', args.input)
        messages = _get_msgs(mido_util.read_syx_file(infile))
else:
    with mido_util.open_input(args.input,
                              args.guessport, args.virtual) as inport:
        logger.info('Reading from port %r', inport.name)
        messages = _get_msgs(inport)

# eprint('Writing file', args.outfile)

if args.plaintext:
    logger.info('Writing hex to stdout')
    # Force ASCII
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="ascii")
    mido_util.writeout_hex(out, messages)
else:
    logger.info('writing bytes to stdout')
    mido_util.writeout_bytes(sys.stdout.buffer, messages)
sys.stdout.flush()

logger.info('Done!')
