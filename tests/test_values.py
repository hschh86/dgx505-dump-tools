import pytest

from commons import values, maps
from commons.messages import controls, controlstate, wrappers, voices, chords


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
        assert values.ENHARMONIA[note] == i
    
    for a, b in [('Cb', 'B♮'), ('F', 'E#'), ('G♯', 'A♭')]:
        assert (values.ENHARMONIA[values.RootNote.from_name(a)] 
            == values.ENHARMONIA[values.RootNote.from_name(b)])

def test_voices():
    for n in [1, 2, 3, 122, 136, 200, 494]:
        assert voices.from_number(n).number == n

    for n in [0, 495]:
        with pytest.raises(KeyError):
            voices.from_number(n)

def test_chords():
    for n in [0x00, 0x22, 0x2A]:
        assert chords.CHORDS.codes[n].code == n
