import pytest

from commons.util import (pack_seven, pack_variable_length,
                          unpack_variable_length, unpack_seven,
                          reconstitute, reconstitute_all,
                          lazy_readonly_property,
                          lazy_property,
                          lazy_readonly_setup_property,
                          cumulative_slices,
                          LazySequence
                          )


def test_seven():
    examples = [(b'\x35\x7E', (0x35 << 7) + 0x7E),
                (b'\x10\x03\x00', 2**18 + (3 << 7)),
                (b'\x10\x00', 0x800),
                (b'\x08\x68', 0x468),
                (b'\x7F\x7F\x7F\x7F', 0x0FFFFFFF),
                (b'\x00', 0)]
    for a, b in examples:
        assert unpack_seven(a) == b
        assert pack_seven(b) == a
        assert pack_seven(b, 5) == a.rjust(5, b'\x00')

    assert unpack_seven(b'\x00'*5+b'\x3B') == 0x3B

    with pytest.raises(ValueError):
        unpack_seven(b'\x80')

    with pytest.raises(ValueError):
        pack_seven(-1)
    with pytest.raises(ValueError):
        pack_seven(2**8, length=1)


def test_reconstitute():
    examples = [(b'\x1A'*7+b'\x40', b'\x9A'+b'\x1A'*6),
                (b'\x00'*7+b'\x7F', b'\x80'*7),
                (b'\x00\x11\x23\x3F\x4F\x5C\x61\x4C',
                 b'\x80\x11\x23\xBF\xCF\x5C\x61')]
    for a, b in examples:
        assert reconstitute(a) == b
    for a in [b'\x00\x01', b'\x00\x00\x00\x90\x00\x00\x00\x00']:
        with pytest.raises(ValueError):
            reconstitute(a)

    for seq in [(0, 1), (2, 1, 0), (2, 2, 0, 2)]:
        a = b''.join(examples[n][0] for n in seq)
        b = b''.join(examples[n][1] for n in seq)
        assert reconstitute_all(a) == b
    for a in [b'\xC0'*8, b'\x00'*12, b'\x00'*15+b'\xFF']:
        with pytest.raises(ValueError):
            reconstitute(a)


def test_vl():
    for a in [b'\x00', b'\x23', b'\x6E', b'\x7F']:
        assert unpack_variable_length(a) == a[0]
        assert pack_variable_length(a[0]) == a
    examples = [(b'\xB5\x7E', (0x35 << 7) + 0x7E),
                (b'\x90\x83\x00', 2**18 + (3 << 7)),
                (b'\x90\x00', 0x800),
                (b'\x88\x68', 0x468),
                (b'\xFF\xFF\xFF\x7F', 0x0FFFFFFF)]
    for a, b in examples:
        assert unpack_variable_length(a) == b
        assert pack_variable_length(b) == a

    a, b = (b'\x81\x80\x80\x80\x00', 2**28)
    assert unpack_variable_length(a, False) == b
    assert pack_variable_length(b, False) == a
    with pytest.raises(ValueError):
        assert unpack_variable_length(a)
    with pytest.raises(ValueError):
        assert pack_variable_length(b)

    for a in [-1, 2**28]:
        with pytest.raises(ValueError):
            pack_variable_length(a)


class SomeObject(object):
    pass


def test_lazy_readonly_property():

    class MyClass(object):
        def __init__(self):
            self.counter = 0

        @property
        def unlazy_prop(self):
            self.counter += 1
            return SomeObject()

        @lazy_readonly_property
        def lazy_prop(self):
            """somestring"""
            self.counter += 1
            return SomeObject()

    inst1 = MyClass()
    assert inst1.counter == 0
    assert inst1.unlazy_prop is not inst1.unlazy_prop
    assert inst1.counter == 2
    assert inst1.lazy_prop is inst1.lazy_prop
    assert inst1.counter == 3
    with pytest.raises(AttributeError):
        inst1.lazy_prop = None
    inst2 = MyClass()
    assert inst1.lazy_prop is not inst2.lazy_prop
    assert MyClass.lazy_prop.__doc__ == "somestring"


def test_lazy_property():

    class MyClass(object):
        def __init__(self):
            self.counter = 0

        @property
        def unlazy_prop(self):
            self.counter += 1
            return SomeObject()

        @lazy_property
        def lazy_prop(self):
            """somestring"""
            self.counter += 1
            return SomeObject()

    inst1 = MyClass()
    assert inst1.counter == 0
    assert inst1.unlazy_prop is not inst1.unlazy_prop
    assert inst1.counter == 2
    assert inst1.lazy_prop is inst1.lazy_prop
    assert inst1.counter == 3
    inst2 = MyClass()
    assert inst1.lazy_prop is not inst2.lazy_prop
    assert MyClass.lazy_prop.__doc__ == "somestring"


def test_lazy_readonly_setup_property():
    class MyClass(object):
        def __init__(self):
            self.counter = 0

        def _setup(self):
            self._salt = SomeObject()
            self._vinegar = SomeObject()
            self.counter += 1

        salt = lazy_readonly_setup_property('_salt', _setup, "salt")
        vinegar = lazy_readonly_setup_property('_vinegar', _setup, "vinegar")

    inst1 = MyClass()
    assert inst1.counter == 0
    assert inst1.salt is inst1.salt
    assert inst1.vinegar is inst1.vinegar
    assert inst1.counter == 1

    inst2 = MyClass()
    assert inst2.counter == 0
    assert inst2.vinegar is inst2.vinegar
    assert inst2.salt is inst2.salt
    assert inst2.counter == 1

    assert MyClass.salt.__doc__ == "salt"
    assert MyClass.vinegar.__doc__ == "vinegar"


def test_cumulative_slices():
    test_string = "01234567890123456789"
    lengths = [4, 3, 2, 7, 1, 0, 5]
    substrs = ["1234", "567", "89", "0123456", "7", "", "89"]
    slices = cumulative_slices(lengths, 1)
    for substr, tslice in zip(substrs, slices):
        assert substr == test_string[tslice]


def test_lazy_sequence():
    counter = 0

    def func(n):
        nonlocal counter
        counter += 1
        return n+1

    seq = LazySequence(5, func)
    assert counter == 0
    assert seq._list[3] is None
    assert seq[3] == 4
    assert seq._list[3] == 4
    assert seq[3] == 4
    assert counter == 1
    assert seq.index(5) == 4
    assert counter > 1
