import json
import os
from pathlib import Path
from verinfast.agent import Agent


def test_scan():
    file_path = Path(__file__)
    test_folder = file_path.parent
    repo_name = "test_tsx"
    output_path = test_folder.joinpath("results").joinpath(repo_name + ".stats.json")  # noqa: E501
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
