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
str_path = str(test_folder.joinpath("str_conf.yaml").absolute())


@patch("verinfast.user.__get_input__", return_value="y")
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
    assert agent.config.use_uuid is True, f"Expected True, config {agent.config}"
    get_url = agent.uploader.make_upload_path("scan_id", report=agent.config.reportId)
    assert (
        get_url == "/report/uuid/9a6e8696-f93a-4402-a64e-342ccb37592b/CorsisCode"
    ), get_url
    agent.scan()
    assert Path(results_dir).exists()
    # Make sure there are no .json results files
    results_path = Path(results_dir)
    assert results_path.exists()

    # Check if there are any JSON files
    json_files = list(results_path.glob("*.json"))
    assert not json_files, f"Found JSON files: {json_files}"

    # Since this test creates it's on DebubLog, the results
    # dir will have two log files. One is timestamped and is
    # the start of the regular log the the agent creates on start.
    # The other is the debug log created by this test, "log.txt"
    assert "/log.txt" in agent.debug.file
    with open(agent.debug.file) as f:
        logText = f.read()
    assert "Error" not in logText
    assert "File does not exist:" in logText
    # Since this test does not run a real scan, the debug log
    # will have errors about file uploads. Confirm it attempts
    # to upload all the files.
    upload_fail_prefix = "File does not exist: "
    upload_fail_prefix = upload_fail_prefix + str(results_dir) + "/"
    assert upload_fail_prefix + "small-test-repo.git.git.log.json" in logText
    assert upload_fail_prefix + "small-test-repo.git.sizes.json" in logText
    assert upload_fail_prefix + "small-test-repo.git.stats.json" in logText
    assert upload_fail_prefix + "small-test-repo.git.findings.json" in logText
    assert upload_fail_prefix + "small-test-repo.git.dependencies.json" in logText
