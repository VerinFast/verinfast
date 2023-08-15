import json

from verinfast.dependencies.walk import walk
from verinfast.dependencies.walkers.classes import Entry

output_path = "./dependencies.json"


def test_walk():
    output_path = walk(path="./tests/", output_file="./dependencies.json")
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        assert first_dep['name'] == 'simple-test-package'
    return True


def test_entity():
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "ISC"
