import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog
import verinfast.user
from verinfast.dependencies.walk import walk
from verinfast.dependencies.walkers.classes import Entry

file_path = Path(__file__)
test_folder = file_path.parent
docker_folder = test_folder.joinpath("fixtures/docker")
results_dir = test_folder.joinpath("results").absolute()
composer_config_path = str(test_folder.joinpath("composer.yaml").absolute())


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


def test_dockerfile_exists():
    docker_file_path = docker_folder.joinpath("Dockerfile")
    assert Path.exists(docker_file_path)


def test_walk():
    folder_path = test_folder.joinpath("fixtures/npm_walker").absolute()
    file_path = folder_path.joinpath("package.json")

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
        assert first_dep["name"] == "simple-test-package"

    os.remove(output_path)
    assert not Path(output_path).exists()
    node_modules = folder_path.joinpath("node_modules")
    shutil.rmtree(node_modules)
    os.remove(folder_path.joinpath("package-lock.json"))
    return None


def test_entity():
    folder_path = test_folder.joinpath("fixtures/nuget_walker").absolute()
    file_path = folder_path.joinpath("test.csproj")
    output_file = test_folder.joinpath("dependencies2.json")
    assert file_path.exists(), "Manifest doesn't exist"
    shutil.rmtree(output_file, ignore_errors=True)
    try:
        os.remove(output_file)
    except:
        pass
    assert not output_file.exists(), "Results file exists"

    output_path = walk(
        path=str(folder_path), output_file=output_file, logger=enabled_logger(False)
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1, f"Output is empty: {output_file}"
        first_dep = output[0]
        e = Entry(**first_dep)
        assert e.license == "MIT"
        found_Cosmos = False
        for d in output:
            if d["name"] == "Microsoft.Azure.Cosmos":
                found_Cosmos = True
                assert d["license"] == "https://aka.ms/netcoregaeula"
        assert found_Cosmos
    os.remove(output_path)
    assert not Path(output_path).exists()

    return None


# def test_ruby():
#     output_path = walk(
#         path=test_folder.joinpath("fixtures/gemwalker"),
#         output_file="./dependencies.json",
#         logger=logger
#     )
#     with open(output_path) as output_file:
#         output = json.load(output_file)
#         assert len(output) >= 1
#         first_dep = output[0]
#         e = Entry(**first_dep)
#         assert e.license == "ISC"
#         found_rubocop = False
#         for d in output:
#             if d["name"] == "rubocop-ast":
#                 found_rubocop = True
#                 assert d["specifier"] == "*"
#         assert found_rubocop
#         found_aasm = False
#         for d in output:
#             if d["name"] == "aasm":
#                 found_aasm = True
#                 assert d["specifier"] == "*"
#         assert found_aasm
#         found_bad_source_type = False
#         found_source_single_quote = False
#         for d in output:
#             if type(d["source"]) is dict:
#                 found_bad_source_type = True
#             elif d["source"].find("'") != -1:
#                 found_source_single_quote = True
#         assert not found_bad_source_type
#         assert not found_source_single_quote

#     return None


# def test_python():
#     output_path = walk(
#         path=test_folder.joinpath("fixtures/python_walker"),
#         output_file="./dependencies.json",
#         logger=logger
#     )
#     with open(output_path) as output_file:
#         output = json.load(output_file)
#         assert len(output) >= 1
#         first_dep = output[0]
#         e = Entry(**first_dep)
#         assert e.license == "ISC"
#         found_azure_identity = False
#         for d in output:
#             if d["name"] == "azure-identity":
#                 found_azure_identity = True
#                 assert d["source"] == "pip"
#         assert found_azure_identity
#         found_azure_core = False
#         for d in output:
#             if d["name"] == "azure-core":
#                 found_azure_core = True
#                 assert d["source"] == "pip"
#         assert found_azure_core

#     return None


def test_docker():
    output_path = walk(
        path=docker_folder,
        output_file="./dependencies.json",
        logger=enabled_logger(False),
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        found_ubuntu_base_image = False
        for d in output:
            if d["name"] == "ubuntu":
                found_ubuntu_base_image = True
                assert d["specifier"] == "trusty"
                assert d["source"] == "Dockerfile"
        assert found_ubuntu_base_image
    os.remove(output_path)

    return None


def test_composer():
    folder_path = test_folder.joinpath("fixtures/composer_walker").absolute()
    file_path = folder_path.joinpath("composer.json")
    assert file_path.exists(), "Manifest doesn't exist"

    output_file_path = test_folder.joinpath("dependencies3.json")
    try:
        os.remove(output_file_path)
    except:
        pass

    output_path = walk(
        path=folder_path, output_file=output_file_path, logger=enabled_logger(False)
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1

    os.remove(output_path)

    return None


def test_go():
    folder_path = test_folder.joinpath("fixtures/go_walker").absolute()
    file_path = folder_path.joinpath("go.sum")
    assert file_path.exists(), "Manifest doesn't exist"

    output_file_path = test_folder.joinpath("dependencies4.json")
    try:
        os.remove(output_file_path)
    except FileNotFoundError:
        pass

    output_path = walk(
        path=folder_path, output_file=output_file_path, logger=enabled_logger(False)
    )
    with open(output_path) as output_file:
        output = json.load(output_file)
        assert len(output) >= 1
        assert output[0]["name"] == "cloud.google.com/go"
        assert output[0]["source"] == "Go"
        assert output[0]["specifier"] == "v0.26.0"

    os.remove(output_path)

    return None


@patch("verinfast.user.__get_input__", return_value="y")
def test_composer_config(self):
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    assert verinfast.user.initial_prompt is not None
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config(composer_config_path)
    config.output_dir = results_dir
    agent.config = config
    agent.config.shouldUpload = False
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    assert Path(results_dir).exists() is True
    expected_files = [
        "CssToInlineStyles.git.dependencies.json",
        "laravel.git.dependencies.json",
    ]
    for f in expected_files:
        expected_file = results_dir.joinpath(f)
        assert expected_file.exists(), f"{expected_file} does not exist"
