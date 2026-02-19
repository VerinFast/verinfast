import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog
import verinfast.user

file_path = Path(__file__)
test_folder = file_path.parent.absolute()
results_dir = test_folder.joinpath("results").absolute()


def _mock_get_gcp_instances(sub_id, path_to_output="./", dry=False):
    instances_file = os.path.join(path_to_output, f"gcp-instances-{sub_id}.json")
    utilization_file = os.path.join(
        path_to_output, f"gcp-instances-{sub_id}-utilization.json"
    )
    instances = {
        "metadata": {"provider": "gcp", "account": str(sub_id)},
        "data": [
            {
                "id": "1234567890",
                "name": "test-instance",
                "state": "RUNNING",
                "type": "e2-medium",
                "zone": "us-central1-a",
                "region": "us-central1",
                "subnet": "default",
                "architecture": "x86_64",
                "vpc": "default",
                "publicIp": "35.0.0.1",
            }
        ],
    }
    utilization = {
        "metadata": {"provider": "gcp", "account": str(sub_id)},
        "data": [
            {
                "id": "1234567890",
                "metrics": [
                    {
                        "timestamp": 1700000000 + (h * 3600),
                        "cpu": {"minimum": 0.1, "average": 0.5, "maximum": 1.0},
                    }
                    for h in range(100)
                ],
            }
        ],
    }
    if not dry:
        with open(instances_file, "w") as f:
            json.dump(instances, f, indent=4)
        with open(utilization_file, "w") as f:
            json.dump(utilization, f, indent=4)
    return instances_file


def _mock_get_gcp_blocks(sub_id, path_to_output="./", dry=False):
    output_file = os.path.join(path_to_output, f"gcp-storage-{sub_id}.json")
    data = {
        "metadata": {"provider": "gcp", "account": str(sub_id)},
        "data": [
            {"name": "test-bucket", "size": 100000, "public": False}
        ],
    }
    if not dry:
        with open(output_file, "w") as f:
            json.dump(data, f, indent=4)
    return output_file


def _mock_check_dependency(self, cmd, name):
    return True


@patch("verinfast.user.__get_input__", return_value="y")
@patch("verinfast.agent.get_gcp_instances", side_effect=_mock_get_gcp_instances)
@patch("verinfast.agent.get_gcp_blocks", side_effect=_mock_get_gcp_blocks)
@patch.object(Agent, "checkDependency", _mock_check_dependency)
def test_gcp_scan(mock_user, mock_instances, mock_blocks):
    assert verinfast.user.initial_prompt is not None
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
