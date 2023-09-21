import json
from pathlib import Path

from pygments_tsx.tsx import patch_pygments

from verinfast.dependencies.walk import walk
from verinfast.dependencies.walkers.classes import Entry

file_path = Path(__file__)
test_folder = file_path.parent

patch_pygments()


def test_walk():
    output_path = walk(path=test_folder, output_file="./dependencies.json")
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        assert first_dep['name'] == 'simple-test-package'
    return True


def test_entity():
    output_path = walk(path="./tests/", output_file="./dependencies.json")
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "ISC"

    return True
