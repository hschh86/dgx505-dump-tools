import pytest
import json

import extractor as e
from commons.exceptions import MessageSequenceError, NotRecordedError


@pytest.fixture(scope='module')
def ffab():
    ffa = e._read_dump_from_filename('test_data/dumptestfull.syx')
    ffb = e._read_dump_from_filename('test_data/dumptestfull.txt')
    return ffa, ffb


@pytest.fixture(scope='module')
def ffcd():
    ffc = e._read_dump_from_filename(
        'test_data/dumptestpartial.syx', songonly=True)
    ffd = e._read_dump_from_filename(
        'test_data/dumptestpartial.txt', songonly=True)
    return ffc, ffd


@pytest.fixture(scope='module')
def jcereal():
    with open('test_data/dump.json') as dj:
        json_cereal = json.load(dj)
    return json_cereal


def test_equivalence(ffab, ffcd, jcereal):
    assert ffab[0]._cereal() == ffab[1]._cereal() == jcereal
    assert ffcd[0]._cereal() == ffcd[1]._cereal()
    assert ffab[0].song_data._cereal() == ffcd[1].song_data._cereal()


def test_incomplete():
    with pytest.raises(MessageSequenceError):
        e._read_dump_from_filename('test_data/dumptestpartial.syx')
    with pytest.raises(MessageSequenceError):
        e._read_dump_from_filename('test_data/dumptestpartial.txt')


def test_midi(ffab, ffcd):
    assert ffab[1].song_data.songs[0].midi == ffcd[0].song_data.songs[0].midi

    with pytest.raises(NotRecordedError):
        ffab[0].song_data.songs[3].midi

    with open('test_data/UserSong2.mid', 'rb') as u2m:
        us2 = u2m.read()
    assert us2 == ffcd[1].song_data.songs[1].midi
