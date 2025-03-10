import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog
import verinfast.user


@patch("verinfast.user.__get_input__", return_value="y")
def test_gcp_scan(self):
    assert verinfast.user.initial_prompt is not None
    file_path = Path(__file__)
    test_folder = file_path.parent.absolute()
    results_dir = test_folder.joinpath("results").absolute()
    cfg_path = test_folder.joinpath("gcp_conf.yaml").absolute()
    agent = Agent()
    config = Config(cfg_path=str(cfg_path))
    assert config.cfg_path == str(cfg_path)
    assert config.config is not FileNotFoundError
    assert "modules" in config.config
    sub_id = config.config["modules"]["cloud"][0]["account"]
    config.output_dir = str(results_dir)
    config.runGit = False
    agent.config = config
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    assert agent.config.output_dir == str(results_dir)
    assert agent.config.dry is False
    assert agent.config.runGit is False
    assert len(agent.config.modules.cloud) > 0
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
    assert Path(results_dir).exists() is False
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.scan()
    assert Path(results_dir).exists() is True
    with open(results_dir.joinpath(f"gcp-instances-{sub_id}.json")) as f:
        instances = json.load(f)
        assert len(instances["data"]) >= 1
    with open(results_dir.joinpath(f"gcp-instances-{sub_id}-utilization.json")) as f:
        utilization = json.load(f)
        for u in utilization["data"]:
            assert isinstance(u["id"], str)
