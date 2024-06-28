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
    assert agent.config.use_uuid is True
    agent.config.dry = True
    agent.config.shouldUpload = True
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.uploader.config = config.upload_conf
    assert agent.config.use_uuid is True, f"Expected True, config {agent.config}"  # noqa: E501
    get_url = agent.uploader.make_upload_path("scan_id", report=agent.config.reportId)  # noqa: E501
    assert get_url == "/report/uuid/9a6e8696-f93a-4402-a64e-342ccb37592b/CorsisCode", get_url  # noqa: E501
    agent.scan()
    assert Path(results_dir).exists()
    files = os.listdir(results_dir)
    assert len(files) == 1
    with open(agent.debug.logFile) as f:
        logText = f.read()
        assert "Error" not in logText
        assert "File does not exist:" in logText
