import json
from pathlib import Path

from pygments_tsx.tsx import patch_pygments

from verinfast.dependencies.walk import walk
from verinfast.dependencies.walkers.classes import Entry

file_path = Path(__file__)
test_folder = file_path.parent

patch_pygments()


def logger(msg, **kwargs):
    print(msg)
    print(kwargs)


def test_walk():
    output_path = walk(
        path=test_folder,
        output_file="./dependencies.json",
        logger=logger
        )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        assert first_dep['name'] == 'simple-test-package'
    return None


def test_entity():
    output_path = walk(
        path=test_folder,
        output_file="./dependencies.json",
        logger=logger
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "ISC"
        found_Cosmos = False
        for d in output:
            if d["name"] == "Microsoft.Azure.Cosmos":
                found_Cosmos = True
                assert d["license"] == "https://aka.ms/netcoregaeula"
        assert found_Cosmos

    return None


def test_ruby():
    output_path = walk(
        path=test_folder,
        output_file="./dependencies.json",
        logger=logger
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "ISC"
        found_azure_identity = False
        for d in output:
            if d["name"] == "rubocop-ast":
                found_azure_identity = True
                assert d["specifier"] == "*"
        assert found_azure_identity
        found_azure_core = False
        for d in output:
            if d["name"] == "aasm":
                found_azure_core = True
                assert d["specifier"] == "*"
        assert found_azure_core

    return None


def test_python():
    output_path = walk(
        path=test_folder,
        output_file="./dependencies.json",
        logger=logger
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "ISC"
        found_azure_identity = False
        for d in output:
            if d["name"] == "azure-identity":
                found_azure_identity = True
                assert d["source"] == "pip"
        assert found_azure_identity
        found_azure_core = False
        for d in output:
            if d["name"] == "azure-core":
                found_azure_core = True
                assert d["source"] == "pip"
        assert found_azure_core

    return None
