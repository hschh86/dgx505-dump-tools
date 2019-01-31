import pytest

from commons import enums, maps
from commons.messages import controls, controlstate, wrappers, voices


def test_notes():
    assert str(enums.NoteValue(0)) == "000(C-2)"
    assert str(enums.NoteValue(21)) == "021(A-1)"
    assert str(enums.NoteValue(60)) == "060(C3)"
    assert str(enums.NoteValue(108)) == "108(C7)"
    assert str(enums.NoteValue(126)) == "126(F#8)"
    assert str(enums.NoteValue(0x7F)) == "127(G8)"