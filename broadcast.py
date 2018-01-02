"""
broadcast.py

Basically, the opposite of slurp.py.
Keep in mind that the times are only approximate
"""

import time
import argparse
import operator

from commons import util, mido_util

argparser = argparse.ArgumentParser(
    description="Dumps contents of a text mido message stream file "
                "to a midi port. "
                "Time attribute = time elapsed in seconds")

portargs = argparser.add_mutually_exclusive_group()
portargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
portargs.add_argument(
    '-v', '--virtual', action='store_true',
    help='Use virtual port')

argparser.add_argument(
    '-p', '--port', type=str,
    help="Port to write to (run 'mido-ports' to list available ports)")
argparser.add_argument(
    '-s', '--speedup', type=float, default='1',
    help="speed multiplier")

waitgroup = argparser.add_mutually_exclusive_group()
waitgroup.add_argument(
    '-n', '--nowait', action='store_true',
    help='Ignore the first time attr, stream out with no initial delay')
waitgroup.add_argument(
    '-i', '--ignoretime', action='store_true',
    help='Ignore all time attrs, just stream out messages as fast as possible,'
         ' i.e. 3125 bytes/second-ish. Can be sped up using speedup argument')

argparser.add_argument(
    '--prompt', action='store_true',
    help='prompt before playback')

argparser.add_argument(
    'filename', type=str,
    help="file to read from")

args = argparser.parse_args()

DEFAULT_BYTERATE = 3125

with open(args.filename, 'rt') as infile:
    msgs = list(mido_util.readin_strings(infile))

# Time manipulation time.
# sort messages by time, just in case.
msgs.sort(key=operator.attrgetter('time'))

if args.speedup > 0:
    bytewait = 1/(DEFAULT_BYTERATE*args.speedup)
else:
    bytewait = 0

# compute the deltas.
delta_message_tuples = []
msg = msgs[0]
if args.nowait or args.ignoretime:
    wait = 0
else:
    wait = msg.time/args.speedup
delta_message_tuples.append((wait, msg))
if args.ignoretime:
    for last, msg in util.iter_pairs(msgs):
        wait = len(last)*bytewait
        delta_message_tuples.append((wait, msg))
else:
    for last, msg in util.iter_pairs(msgs):
        # just completely ignore the bytewait?
        wait = (msg.time - last.time)/args.speedup
        delta_message_tuples.append((wait, msg))

with mido_util.open_output(
        args.port, args.guessport, args.virtual, autoreset=True) as outport:
    print("writing to port", outport.name)
    if args.prompt:
        input("Press enter to start")
    for wait, msg in delta_message_tuples:
        time.sleep(wait)
        outport.send(msg)
    time.sleep(len(msg)*bytewait)
    print("finished")
