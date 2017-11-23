# temporary, I hope
from time import sleep
import argparse

import mido
from commons import mido_util


argparser = argparse.ArgumentParser(
    description="Dumps contents of a binary midi message stream file "
                "to a virtual midi port")

argparser.add_argument(
    'filename', type=str,
    help="file to read from")

argparser.add_argument(
    'portname', type=str,
    help="name to use for virtual port")

argparser.add_argument(
    '--byterate', type=float, default='3125',
    help="simulated byte-rate, bytes per second (uses sleeping)")

args = argparser.parse_args()

do_sleeping = args.byterate > 0


with open(args.filename, 'rb') as infile:
    msgs = list(mido_util.readin_bytes(infile))

with mido.open_output(args.portname, virtual=True) as outport:
    while True:
        input("Press enter to start")
        for msg in msgs:
            outport.send(msg)
            if do_sleeping:
                sleep(len(msg)/args.byterate)
        print("finished")
