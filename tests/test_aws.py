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


def _mock_get_aws_costs(
    targeted_account, start, end, path_to_output, log, profile=None, dry=False
):
    output_file = os.path.join(path_to_output, f"aws-cost-{targeted_account}.json")
    data = {
        "metadata": {"provider": "aws", "account": str(targeted_account)},
        "data": [
            {
                "Date": f"2024-{(i % 12) + 1:02d}-01",
                "Group": "Amazon EC2",
                "Cost": "10.00",
                "Currency": "USD",
            }
            for i in range(120)
        ],
    }
    if not dry:
        with open(output_file, "w") as f:
            json.dump(data, f, indent=4)
    return output_file


def _mock_get_aws_instances(sub_id, path_to_output="./", dry=False, **kwargs):
    instances_file = os.path.join(path_to_output, f"aws-instances-{sub_id}.json")
    utilization_file = os.path.join(
        path_to_output, f"aws-instances-{sub_id}-utilization.json"
    )
    instances = {
        "metadata": {"provider": "aws", "account": str(sub_id)},
        "data": [
            {
                "id": f"i-{i:012x}",
                "name": f"instance-{i}",
                "state": "running",
                "type": "t3.medium",
                "zone": "us-east-1a",
                "region": "us-east-1",
                "subnet": "subnet-abc",
                "architecture": "x86_64",
                "vpc": "vpc-123",
                "publicIp": f"10.0.0.{i}",
            }
            for i in range(1, 7)
        ],
    }
    utilization = {
        "metadata": {"provider": "aws", "account": str(sub_id)},
        "data": [
            {
                "id": "i-000000000001",
                "metrics": [
                    {
                        "timestamp": 1700000000 + (h * 3600),
                        "cpu": {"minimum": 0.5, "average": 1.2, "maximum": 3.4},
                    }
                    for h in range(250)
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


def _mock_get_aws_blocks(sub_id, path_to_output="./", log=None, dry=False, **kwargs):
    output_file = os.path.join(path_to_output, f"aws-storage-{sub_id}.json")
    data = {
        "metadata": {"provider": "aws", "account": str(sub_id)},
        "data": [
            {
                "name": "test-bucket",
                "size": 500000,
                "retention": "Enabled",
                "public": False,
                "permissions": [],
            }
        ],
    }
    if not dry:
        with open(output_file, "w") as f:
            json.dump(data, f, indent=4)
    return output_file


def _mock_find_profile(targeted_account, log):
    return "default"


def _mock_check_dependency(self, cmd, name):
    return True


@patch("verinfast.user.__get_input__", return_value="y")
@patch("verinfast.agent.get_aws_costs", side_effect=_mock_get_aws_costs)
@patch("verinfast.agent.get_aws_instances", side_effect=_mock_get_aws_instances)
@patch("verinfast.agent.get_aws_blocks", side_effect=_mock_get_aws_blocks)
@patch("verinfast.agent.find_profile", side_effect=_mock_find_profile)
@patch.object(Agent, "checkDependency", _mock_check_dependency)
def test_aws_scan(mock_user, mock_costs, mock_instances, mock_blocks, mock_profile):
    sub_id = 436708548746
    assert verinfast.user.initial_prompt is not None
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

    # Verify cost output
    with open(results_dir.joinpath(f"aws-cost-{sub_id}.json")) as f:
        costs = json.load(f)
        assert costs["metadata"]["provider"] == "aws"
        assert costs["metadata"]["account"] == str(sub_id)
        assert len(costs["data"]) >= 100

    # Verify instances output
    with open(results_dir.joinpath(f"aws-instances-{sub_id}.json")) as f:
        instances = json.load(f)
        assert len(instances["data"]) >= 5

    # Verify utilization output
    with open(results_dir.joinpath(f"aws-instances-{sub_id}-utilization.json")) as f:
        utilization = json.load(f)
        assert len(utilization["data"]) >= 1
        assert len(utilization["data"][0]["metrics"]) >= 200

    # Verify storage output
    with open(results_dir.joinpath(f"aws-storage-{sub_id}.json")) as f:
        storage = json.load(f)
        assert len(storage["data"]) >= 1


@patch("verinfast.user.__get_input__", return_value="y")
@patch("verinfast.agent.get_aws_costs", side_effect=_mock_get_aws_costs)
@patch("verinfast.agent.get_aws_instances", side_effect=_mock_get_aws_instances)
@patch("verinfast.agent.get_aws_blocks", side_effect=_mock_get_aws_blocks)
@patch("verinfast.agent.find_profile", side_effect=_mock_find_profile)
@patch.object(Agent, "checkDependency", _mock_check_dependency)
def test_aws_dash(mock_user, mock_costs, mock_instances, mock_blocks, mock_profile):
    sub_id = "436708548746"
    assert verinfast.user.initial_prompt is not None
    cfg_path = test_folder.joinpath("aws_dash.yaml").absolute()
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

    # Dashed account "4367-0854-8746" normalizes to "436708548746"
    with open(results_dir.joinpath(f"aws-cost-{sub_id}.json")) as f:
        costs = json.load(f)
        assert costs["metadata"]["provider"] == "aws"
        assert len(costs["data"]) >= 1
    with open(results_dir.joinpath(f"aws-instances-{sub_id}.json")) as f:
        instances = json.load(f)
        assert len(instances["data"]) >= 1
    with open(results_dir.joinpath(f"aws-storage-{sub_id}.json")) as f:
        storage = json.load(f)
        assert len(storage["data"]) >= 1


@patch("verinfast.user.__get_input__", return_value="y")
@patch("verinfast.agent.get_aws_costs", side_effect=_mock_get_aws_costs)
@patch("verinfast.agent.get_aws_instances", side_effect=_mock_get_aws_instances)
@patch("verinfast.agent.get_aws_blocks", side_effect=_mock_get_aws_blocks)
@patch("verinfast.agent.find_profile", side_effect=_mock_find_profile)
@patch.object(Agent, "checkDependency", _mock_check_dependency)
def test_aws_profile(mock_user, mock_costs, mock_instances, mock_blocks, mock_profile):
    assert verinfast.user.initial_prompt is not None
    cfg_path = test_folder.joinpath("aws_profile.yaml").absolute()
    agent = Agent()
    config = Config(cfg_path=str(cfg_path))
    assert config.cfg_path == str(cfg_path)
    assert config.config is not FileNotFoundError
    assert "modules" in config.config

    # Verify profile is parsed from config
    assert "profile" in config.config["modules"]["cloud"][0]
    assert config.config["modules"]["cloud"][0]["profile"] == "default"

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
    assert not Path(results_dir).exists()
    os.makedirs(agent.config.output_dir, exist_ok=True)
    agent.scan()
