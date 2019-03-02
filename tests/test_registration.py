import pytest
import json

from commons.mido_util import read_syx_file
from commons.dumpdata.messages import RegDumpSection


@pytest.mark.parametrize("datafile, valuefile", [
    ('tests/data/dumps/regtest1.txt', 'tests/data/json/regtest1.json'),
    ('tests/data/dumps/regtest2.txt', 'tests/data/json/regtest2.json'),
    ('tests/data/dumps/regtest3.syx', 'tests/data/json/regtest3.json')
])
def test_reg(datafile, valuefile):
    with open(datafile, 'rb') as infile:
        msgs = read_syx_file(infile)
        dobj = RegDumpSection(msgs).settings
    with open(valuefile, 'r') as vfile:
        sets = json.load(vfile)
    dset = dobj.get_setting(4, 2)
    assert dset.unusual_len() == 0
    for key, value in sets.items():
        assert str(dset[key].value) == value
