import pytest

import extractor as e

def test_seven():
    examples = [(b'\x35\x7E', (0x35 << 7) + 0x7E),
                (b'\x10\x03\x00', 2**18 + (3<<7)),
                (b'\x10\x00', 0x800),
                (b'\x08\x68', 0x468),
                (b'\x7F\x7F\x7F\x7F', 0x0FFFFFFF),
                (b'\x00', 0)]
    for a, b in examples:
        assert e.unpack_seven(a) == b
        assert e.pack_seven(b) == a
        assert e.pack_seven(b, 5) == a.rjust(5, b'\x00')

    assert e.unpack_seven(b'\x00'*5+b'\x3B') == 0x3B

    with pytest.raises(ValueError):
        e.unpack_seven(b'\x80')

    with pytest.raises(ValueError):
        e.pack_seven(-1)
    with pytest.raises(ValueError):
        e.pack_seven(2**8, length=1)

def test_reconstitute():
    examples = [(b'\x1A'*7+b'\x40', b'\x9A'+b'\x1A'*6),
                (b'\x00'*7+b'\x7F', b'\x80'*7),
                (b'\x00\x11\x23\x3F\x4F\x5C\x61\x4C',
                 b'\x80\x11\x23\xBF\xCF\x5C\x61')]
    for a, b in examples:
        assert e.reconstitute(a) == b
    for a in [b'\x00\x01', b'\x00\x00\x00\x90\x00\x00\x00\x00']:
        with pytest.raises(ValueError):
            e.reconstitute(a)

    for seq in [(0, 1), (2, 1, 0), (2, 2, 0, 2)]:
        a = b''.join(examples[n][0] for n in seq)
        b = b''.join(examples[n][1] for n in seq)
        assert e.reconstitute_all(a) == b
    for a in [b'\xC0'*8, b'\x00'*12, b'\x00'*15+b'\xFF']:
        with pytest.raises(ValueError):
            e.reconstitute(a)

def test_vl():
    for a in [b'\x00', b'\x23', b'\x6E', b'\x7F']:
        assert e.unpack_variable_length(a) == a[0]
        assert e.pack_variable_length(a[0]) == a
    examples = [(b'\xB5\x7E', (0x35 << 7) + 0x7E),
                (b'\x90\x83\x00', 2**18 + (3<<7)),
                (b'\x90\x00', 0x800),
                (b'\x88\x68', 0x468),
                (b'\xFF\xFF\xFF\x7F', 0x0FFFFFFF)]
    for a, b in examples:
        assert e.unpack_variable_length(a) == b
        assert e.pack_variable_length(b) == a

    a, b = (b'\x81\x80\x80\x80\x00', 2**28)
    assert e.unpack_variable_length(a, False) == b
    assert e.pack_variable_length(b, False) == a
    with pytest.raises(ValueError):
        assert e.unpack_variable_length(a)
    with pytest.raises(ValueError):
        assert e.pack_variable_length(b)

    for a in [-1, 2**28]:
        with pytest.raises(ValueError):
            e.pack_variable_length(a)
