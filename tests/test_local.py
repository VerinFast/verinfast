import json
from unittest.mock import patch
import os
from pathlib import Path
from verinfast.agent import Agent


@patch("verinfast.user.__get_input__", return_value="y")
def test_local_scan(self):
    file_path = Path(__file__)
    test_folder = file_path.parent
    stats_path = test_folder.joinpath("results").joinpath("tsx_test.stats.json")
    size_path = test_folder.joinpath("results").joinpath("tsx_test.sizes.json")
    findings_path = test_folder.joinpath("results").joinpath("tsx_test.findings.json")
    dependencies_path = test_folder.joinpath("results").joinpath(
        "tsx_test.dependencies.json"
    )
    tsx_path = test_folder.joinpath("tsx_test")

    agent = Agent()
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.config.runGit = True
    agent.config.output_dir = test_folder.joinpath("results")
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.config.config["local_repos"] = [tsx_path.absolute().as_posix()]

    agent.scanRepos()

    with open(stats_path) as output_file:
        output = json.load(output_file)
        assert output is not None

    assert os.path.exists(size_path)
    assert os.path.exists(findings_path)
    assert os.path.exists(dependencies_path)

    return None


@patch("verinfast.user.__get_input__", return_value="y")
def test_local_scan_branch(self):
    file_path = Path(__file__)
    test_folder = file_path.parent
    stats_path = test_folder.joinpath("results").joinpath("tsx_test.stats.json")
    size_path = test_folder.joinpath("results").joinpath("tsx_test.sizes.json")
    findings_path = test_folder.joinpath("results").joinpath("tsx_test.findings.json")
    dependencies_path = test_folder.joinpath("results").joinpath(
        "tsx_test.dependencies.json"
    )
    tsx_path = test_folder.joinpath("tsx_test")

    agent = Agent()
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.config.runGit = True
    agent.config.output_dir = test_folder.joinpath("results")
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.config.config["local_repos"] = [tsx_path.absolute().as_posix() + "@main"]

    agent.scanRepos()

    with open(stats_path) as output_file:
        output = json.load(output_file)
        assert output is not None

    assert os.path.exists(size_path)
    assert os.path.exists(findings_path)
    assert os.path.exists(dependencies_path)

    return None
