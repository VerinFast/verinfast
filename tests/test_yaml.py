import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.upload import Uploader
from verinfast.utils.utils import DebugLog


@patch("verinfast.user.__get_input__", return_value="y")
def test_no_config(self):
    agent = Agent()
    assert agent.config.modules.cloud == []
    assert agent.config.config["local_repos"] == ["./"]


@patch("verinfast.user.__get_input__", return_value="y")
def test_file(self):
    file_path = Path(__file__)
    test_folder = file_path.parent.absolute()
    agent = Agent()
    config = Config()
    config.cfg_path = str(test_folder.joinpath("config.yaml").absolute())
    config.__init__()
    # Test not overwritten
    assert config.cfg_path == str(test_folder.joinpath("config.yaml").absolute())
    assert config.modules.cloud == []
    agent.config = config
    assert agent.config.dry is True
    assert agent.config.runDependencies is False
    assert agent.config.reportId == 0
    assert agent.config.baseUrl == ""
    assert agent.up("logs", report=0) == "/report/0/agent_logs"
    agent.uploader = Uploader(agent.config.upload_conf)
    agent.up = agent.uploader.make_upload_path
    assert agent.up("logs", report=0) == "/report/0/agent_logs"
    assert agent.getloc(config.cfg_path) >= 9


@patch("verinfast.user.__get_input__", return_value="y")
def test_str_results_from_file(self):

    file_path = Path(__file__)
    test_folder = file_path.parent.absolute()
    results_dir = test_folder.joinpath("results").absolute()
    agent = Agent()
    config = Config(str(test_folder.joinpath("str_conf.yaml").absolute()))
    config.output_dir = str(results_dir)
    assert config.runGit
    agent.config = config
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    assert agent.config.output_dir == str(results_dir)
    assert agent.config.dry is False
    assert agent.config.runGit is True
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
    assert Path(results_dir).exists() is False
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.scan()
    assert Path(results_dir).exists() is True
    with open(results_dir.joinpath("small-test-repo.git.filelist.json")) as f:
        file_list = json.load(f)
        assert len(file_list) >= 4
        for myfile in file_list:
            if myfile["name"] == "README.md":
                assert str(myfile["path"]).endswith("README.md")
            assert myfile["name"]
            assert myfile["path"]
    with open(results_dir.joinpath("small-test-repo.git.sizes.json")) as f:
        sizes = json.load(f)
        assert sizes["files"]["."]["size"] >= 34100
        assert sizes["files"]["./README.md"]["ext"] == "md"
    with open(results_dir.joinpath("small-test-repo.git.stats.json")) as f:
        stats = json.load(f)
        for file_name in stats["files"]:
            file_name = str(file_name)
            if file_name.endswith("/temp_repo/README.md"):
                my_file = stats["files"][file_name]
                assert my_file["lang"][0] == "Markdown"
    with open(results_dir.joinpath("small-test-repo.git.findings.json")) as f:
        findings = json.load(f)
        for finding in findings["results"]:
            p = str(finding["path"])
            if p.endswith("semgrep/error.sh"):
                assert finding["start"]["line"] in [5, 10, 16, 19]
