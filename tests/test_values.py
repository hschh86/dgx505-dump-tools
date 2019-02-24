import pytest

from commons import values, maps
from commons.messages import (
    controls, controlstate, wrappers, voices, chords, styles,
    exclusives)


def test_notes():
    assert str(values.NoteValue(0)) == "000(C-2)"
    assert str(values.NoteValue(21)) == "021(A-1)"
    assert str(values.NoteValue(60)) == "060(C3)"
    assert str(values.NoteValue(108)) == "108(C7)"
    assert str(values.NoteValue(126)) == "126(F#8)"
    assert str(values.NoteValue(0x7F)) == "127(G8)"

    assert values.RootNote(values.NoteBase.C) == values.RootNote.from_name('C')
    assert (values.RootNote(values.NoteBase.A, values.NoteAcc.FLAT) 
            == values.RootNote.from_name('Ab')
            == values.RootNote.from_name('A♭'))

    for s in ['GB', ' A', 'h', 'C♭♭']:
        with pytest.raises(ValueError):
            values.RootNote.from_name(s)

    assert values.RootNote(values.NoteBase.E).acc is values.NoteAcc.NAT
    
    with pytest.raises(ValueError):
        values.RootNote(values.NoteAcc.FLAT)

    for i, note in values.ROOT_NOTE_SEQ.items():
        assert values.enharmonia(note) == i
    
    for p in [('Cb', 'B♮'), ('F', 'E#'), ('G♯', 'A♭')]:
        assert values.enharmonic(*map(values.RootNote.from_name, p))
    
    for p in [('A#', 'B'), ('C', 'B')]:
        assert not values.enharmonic(*map(values.RootNote.from_name, p))

def test_voices():
    for n in [1, 2, 3, 122, 136, 200, 494]:
        assert voices.from_number(n).number == n

    for n in [0, 495]:
        with pytest.raises(KeyError):
            voices.from_number(n)

def test_chords():
    for n in [0x00, 0x22, 0x2A]:
        assert chords.CHORDS.codes[n].code == n

def test_styles():
    for n in [1, 2, 8, 22, 135, 136]:
        style = styles.from_number(n)
        assert style.number == n
        assert styles.from_name(style.name) == style

    for n in [0, 137]:
        with pytest.raises(KeyError):
            styles.from_number(n)

def test_exclusives():
    for m, t in [
        (controls.gm_on(), dict(
            type=wrappers.SysEx.GM_ON)),
        (controls.master_tune(0x7F, 0x06), dict(
            type=wrappers.SysEx.MASTER_TUNE, mm=0x7F, ll=0x06, cc=0x00, n=0)),
        (controls.master_vol(0x22), dict(
            type=wrappers.SysEx.MASTER_VOL, ll=0, mm=0x22
        )),
        (controls.xg_on(), dict(
            type=wrappers.SysEx.XG_ON, n=0
        ))
    ]:
        assert exclusives.match_sysex(m) == t


def test_cs():
    s = controlstate.MidiControlState()
    m = controls.gm_on()
    w = s.feed(m)
    assert w.wrap_type is wrappers.SysEx.GM_ON
    assert w.value is None
