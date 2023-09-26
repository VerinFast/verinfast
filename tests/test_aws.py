import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog
import verinfast.user


@patch('verinfast.user.__get_input__', return_value='y')
def test_aws_scan(self):
    sub_id = 436708548746
    assert verinfast.user.initial_prompt is not None
    file_path = Path(__file__)
    test_folder = file_path.parent.absolute()
    results_dir = test_folder.joinpath("results").absolute()
    cfg_path = test_folder.joinpath("aws_conf.yaml").absolute()
    agent = Agent()
    config = Config(cfg_path=str(cfg_path))
    assert config.cfg_path == str(cfg_path)
    assert config.config is not FileNotFoundError
    assert "modules" in config.config
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
    with open(results_dir.joinpath(f"aws-cost-{sub_id}.json")) as f:
        costs = json.load(f)
        assert len(costs["data"]) >= 100
    with open(results_dir.joinpath(f"aws-instances-{sub_id}.json")) as f:
        instances = json.load(f)
        assert len(instances["data"]) >= 5
    with open(
        results_dir.joinpath(f"aws-instances-{sub_id}-utilization.json")
    ) as f:
        utilization = json.load(f)
        v = []
        for u in utilization["data"]:
            if u["id"] == "i-0a3493d5abcdfba4b":
                v = u["metrics"]
        assert len(v) >= 450
    with open(results_dir.joinpath(f"aws-storage-{sub_id}.json")) as f:
        storage = json.load(f)
        v = 0
        for u in storage["data"]:
            if u["name"] == "startupos-test-bucket":
                v = u["size"]
        assert v >= 262183
