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
str_path = str(test_folder.joinpath('str_conf.yaml').absolute())


@patch('verinfast.user.__get_input__', return_value='y')
def test_no_config(self):
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config(str_path)
    config.output_dir = results_dir
    print(agent.config.output_dir)
    agent.config = config
    agent.config.dry = True
    agent.config.shouldUpload = True
    agent.uploader.config = config.upload_conf
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.uploader.config = config.upload_conf
    agent.scan()
    assert Path(results_dir).exists()
    files = os.listdir(results_dir)
    assert len(files) == 1
    with open(agent.debug.logFile) as f:
        logText = f.read()
        assert "Error" not in logText
        assert "File does not exist:" in logText
