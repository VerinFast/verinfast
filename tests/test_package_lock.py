import json

# from unittest.mock import patch
import os
from pathlib import Path

# import shutil

# from verinfast.agent import Agent
# from verinfast.config import Config
# from verinfast.utils.utils import DebugLog
# import verinfast.user
from verinfast.dependencies.walk import walk
from verinfast.dependencies.walkers.package_lock import PackageWalker as PW

# from verinfast.dependencies.walkers.classes import Entry


file_path = Path(__file__)
test_folder = file_path.parent
fixtures_folder = test_folder.joinpath("fixtures")
walker_folder = fixtures_folder.joinpath("package_lock_walker")
results_dir = test_folder.joinpath("results").absolute()


def enabled_logger(flag=True):
    def silent(msg, **kwargs):
        return None

    def logger(msg, **kwargs):
        print(msg)
        print(kwargs)

    if flag:
        return logger
    else:
        return silent


def test_package_lock_exists():
    package_lock_file_path = walker_folder.joinpath("package-lock.json")
    assert package_lock_file_path.exists()


def test_indirect():
    folder_path = walker_folder.absolute()
    file_path = folder_path.joinpath("package-lock.json")

    output_file = test_folder.joinpath("dependencies1.json")
    assert file_path.exists(), "Manifest doesn't exist"
    assert not output_file.exists(), "Results file exists"

    output_path = walk(
        path=folder_path, output_file=output_file, logger=enabled_logger(False)
    )

    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        first_dep = output[0]
        assert first_dep["name"] == "@ampproject/remapping"
        assert first_dep["specifier"] == "2.2.1"

    os.remove(output_path)
    assert not Path(output_path).exists()
    return None


def test_direct():
    packageWalker = PW(
        manifest_type="json",
        logger=enabled_logger(False),
        root_dir=walker_folder,
        manifest_files=["package-lock.json"],
    )
    packageWalker.walk(path=walker_folder)
    assert packageWalker.entries[0].name == "@ampproject/remapping"
