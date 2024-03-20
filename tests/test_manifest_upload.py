import os
from unittest.mock import patch
from pathlib import Path
import shutil

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog

file_path = Path(__file__)
test_folder = file_path.parent.absolute()
results_dir = test_folder.joinpath("results").absolute()
str_path = str(test_folder.joinpath('win_conf.yaml').absolute())


def make_clean_agent():
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config(str_path)
    config.output_dir = results_dir
    agent.config = config
    agent.config.runGit = True
    agent.config.runScan = False
    agent.config.runSizes = False
    agent.config.runStats = False
    agent.config.runDependencies = True
    agent.config.upload_logs = False
    agent.config.shouldUpload = True
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.manifest_uploader = stub_uploader
    agent.upload = noop
    return agent


uploaded = False


def noop(*args, **kwargs):
    pass


def stub_uploader(*args, **kwargs):
    global uploaded
    uploaded = True


@patch('verinfast.user.__get_input__', return_value='y')
def test_should_upload_manifest(self):
    global uploaded
    uploaded = False
    agent = make_clean_agent()
    agent.config.upload_manifest = True
    assert uploaded is False
    agent.log("Test 1 running")
    agent.scan()
    assert uploaded is True


@patch('verinfast.user.__get_input__', return_value='y')
def test_should_not_upload_manifest(self):
    global uploaded
    uploaded = False
    agent = make_clean_agent()
    agent.log("shouldUpload True")
    assert agent.config.upload_manifest is False
    assert uploaded is False
    agent.log("Bullshit")
    agent.scan()
    assert uploaded is False


@patch('verinfast.user.__get_input__', return_value='y')
def test_should_not_upload_manifest_no_uploads(self):
    global uploaded
    uploaded = False
    agent = make_clean_agent()
    agent.config.shouldUpload = False
    agent.config.upload_manifest = True
    agent.log("shouldUpload False")
    assert agent.config.upload_manifest is True
    assert uploaded is False
    agent.scan()
    assert uploaded is False
