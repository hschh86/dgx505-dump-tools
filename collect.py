"""
collect.py

write out bulk dump data to a file
Starts reading from the first sysex message
and stops reading at the first Clock message.

"""
import mido

# simple filter thing
def grab_sysex_until_clock(port):
    """
    generator/filter thing over an iterable of mido messages,
    such as mido ports.
    Discards all messages before the first SysEx,
    then yields all the SysEx messages until a Clock message is sent.
    """
    # discard messages until first sysex
    for message in port:
        if message.type == 'sysex':
            yield message
            break
    # yield messages until next clock
    for message in port:
        if message.type == 'sysex':
            yield message
        elif message.type == 'clock':
            break

def writeout_hex(outfile, messages):
    """
    Write messages as hexadecimal to a (text-mode) file object, one message per line
    Similar to mido.write_syx_file with plaintext=True, except uses a file object
    and doesn't care what type of messages they are
    """
    for message in messages:
        outfile.write(message.hex())
        outfile.write('\n')

def writeout_bytes(outfile, messages):
    """
    Write messages as bytes to a (binary-mode) file object, one message per line
    Similar to mido.write_syx_file with plaintext=False, except uses a file object
    and doesn't care what type of messages they are
    """
    for message in messages:
        outfile.write(message.bin())

if __name__ == "__main__":

    import argparse, sys

    def eprint(*args, **kwargs):
        """Print to stderr."""
        print(*args, file=sys.stderr, **kwargs)

    argparser = argparse.ArgumentParser(description="Writes out bulk dump data to file")
    argparser.add_argument('-p', '--port', type=str,
                           help="Port to read from (run 'mido-ports' to list available ports)")
    argparser.add_argument('outfile', type=str, help="File to write to. Error if file already exists")
    argparser.add_argument('-g', '--guessport', action='store_true',
                           help="Guess which port to use (partial name match on PORT)")
    argparser.add_argument('-t', '--plaintext', action='store_true',
                           help="Write as hexadecimal text instead of binary")
    args = argparser.parse_args()

    if args.guessport and args.port:
        for port in mido.get_input_names():
            if args.port in port:
                inport_name = port
                break
        else:
            raise ValueError('Unable to guess port from {!r}'.format(args.port))
    else:
        inport_name = args.port

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

    with mido.open_input(inport_name) as inport:
        eprint('Reading from port', inport_name)
        messages = []
        for message in grab_sysex_until_clock(inport):
            eprint('Message recieved...')
            messages.append(message)
        eprint('Messages finished')

    eprint('Writing file', args.outfile)
    with outfile:
        if args.plaintext:
            eprint('Writing hex to', args.outfile)
            writeout_hex(outfile, messages)
        else:
            eprint('writing bytes to', args.outfile)
            writeout_bytes(outfile, messages)
    eprint('Done!')
