import json
from unittest.mock import patch
import os
from pathlib import Path
from verinfast.agent import Agent
import verinfast.user


@patch("verinfast.user.__get_input__", return_value="y")
def test_scan(self):
    file_path = Path(__file__)
    test_folder = file_path.parent
    repo_name = "test_tsx"
    output_path = test_folder.joinpath("results").joinpath(repo_name + ".stats.json")
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

    agent.parseRepo(path=tsx_path, repo_name=repo_name)

    with open(output_path) as output_file:
        output = json.load(output_file)
        assert output is not None

    return None


@patch("verinfast.user.__get_input__", return_value="y")
def test_home(self):
    assert verinfast.user.user_home is not None


@patch("verinfast.user.__get_input__", return_value="y")
def test_mock(self):
    assert verinfast.user.__get_input__() == "y"
