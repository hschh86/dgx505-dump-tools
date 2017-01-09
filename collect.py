"""
collect.py

write out bulk dump data to a plain text syx file
Starts reading from the first sysex message 
and stops reading at the first Clock message.

"""
import mido

TESTPORT = 'DGX-505:DGX-505 MIDI 1 20:0'
OUTFILE = 'syxout.txt'

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
            print('START')
            yield message
            break
    # yield messages until next clock
    for message in port:
        if message.type == 'sysex':
            print('CONTINUE')
            yield message
        elif message.type == 'clock':
            print('END')
            break
            

with mido.open_input(TESTPORT) as inport:
    print('Reading from port', TESTPORT)
    message_list = list(grab_sysex_until_clock(inport))
print('Writing file', OUTFILE)
mido.write_syx_file(OUTFILE, message_list, plaintext=True)
print('Done!')

