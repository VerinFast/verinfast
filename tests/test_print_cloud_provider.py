from unittest.mock import patch
from pathlib import Path

from verinfast.agent import Agent
from verinfast.config import Config


def print_cloud(config_file: str):
    file_path = Path(__file__)
    test_folder = file_path.parent.absolute()

    # Create config with the correct path from the start
    config = Config(cfg_path=str(test_folder.joinpath(config_file).absolute()))

    # Verify config was loaded correctly
    assert config.cfg_path == str(test_folder.joinpath(config_file).absolute())
    assert config.modules.cloud

    # create agent with config
    agent = Agent(config=config)
    for provider in agent.config.modules.cloud:
        print(provider)


@patch('verinfast.user.__get_input__', return_value='y')
def test_gcp(self):
    config_file = "gcp_conf.yaml"
    print_cloud(config_file=config_file)
    assert True


@patch('verinfast.user.__get_input__', return_value='y')
def test_aws(self):
    config_file = "aws_conf.yaml"
    print_cloud(config_file=config_file)
    assert True


@patch('verinfast.user.__get_input__', return_value='y')
def test_aws_dash(self):
    config_file = "aws_dash.yaml"
    print_cloud(config_file=config_file)
    assert True
