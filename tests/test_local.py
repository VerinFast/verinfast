import json
from unittest.mock import patch
import os
from pathlib import Path
from verinfast.agent import Agent


@patch("verinfast.user.__get_input__", return_value="y")
def test_local_scan(self):
    file_path = Path(__file__)
    test_folder = file_path.parent
    output_path = test_folder.joinpath("results").joinpath("tsx_test.stats.json")
    tsx_path = test_folder.joinpath("tsx_test")

    agent = Agent()
    agent.config.runGit = False
    agent.config.dry = False
    agent.config.runPygount = False
    agent.config.runScan = False
    agent.config.runSizes = False
    agent.config.runStats = True
    agent.config.output_dir = test_folder.joinpath("results")
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.config.config["local_repos"] = [tsx_path.absolute().as_posix()]

    agent.scanRepos()

    with open(output_path) as output_file:
        output = json.load(output_file)
        assert output is not None

    return None


@patch("verinfast.user.__get_input__", return_value="y")
def test_local_scan_branch(self):
    file_path = Path(__file__)
    test_folder = file_path.parent
    output_path = test_folder.joinpath("results").joinpath("tsx_test.stats.json")
    tsx_path = test_folder.joinpath("tsx_test")

    agent = Agent()
    agent.config.runGit = False
    agent.config.dry = False
    agent.config.runPygount = False
    agent.config.runScan = False
    agent.config.runSizes = False
    agent.config.runStats = True
    agent.config.output_dir = test_folder.joinpath("results")
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.config.config["local_repos"] = [tsx_path.absolute().as_posix() + "@main"]

    agent.scanRepos()

    with open(output_path) as output_file:
        output = json.load(output_file)
        assert output is not None

    return None
