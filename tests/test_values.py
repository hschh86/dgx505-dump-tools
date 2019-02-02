import pytest

from commons import values, maps
from commons.messages import controls, controlstate, wrappers, voices


def test_notes():
    assert str(values.NoteValue(0)) == "000(C-2)"
    assert str(values.NoteValue(21)) == "021(A-1)"
    assert str(values.NoteValue(60)) == "060(C3)"
    assert str(values.NoteValue(108)) == "108(C7)"
    assert str(values.NoteValue(126)) == "126(F#8)"
    assert str(values.NoteValue(0x7F)) == "127(G8)"