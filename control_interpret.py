"""
control_interpret.py

Reads a stream of mido text,  prints out an interpetation of the
control messages. Optionally, can annotate
"""


import argparse
import logging
import sys

from commons import util, mido_util
from commons.messages import controlstate

argparser = argparse.ArgumentParser(
    description="Print out an interpretation of the control messages.")

argparser.add_argument(
    'filename', type=str,
    help="file to read from")

argparser.add_argument(
    '-a', '--annotate', action='store_true',
    help="Print out the original message as well on the same line")


if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('control_interpret')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    stator = controlstate.MidiControlState()

    with util.open_file_stdstream(args.filename, 'rt') as infile:
        try:
            messages = mido_util.readin_strings(infile, comment='#')
            for message in messages:
                wrap = stator.feed(message)
                if args.annotate:
                    sys.stdout.write(str(message))
                    if wrap is not None:
                        sys.stdout.write(' # ')
                        sys.stdout.write(str(wrap))
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                else:
                    if wrap is not None:
                        sys.stdout.write(str(wrap)+'\n')
                        sys.stdout.flush()
        except KeyboardInterrupt:
            logger.info("Stopping on KeyboardInterrupt")