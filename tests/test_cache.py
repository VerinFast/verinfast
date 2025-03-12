import json
import os
from pathlib import Path
import time

from verinfast.agent import Agent
from verinfast.code_scan import run_scan
from verinfast.config import Config
from verinfast.utils.utils import DebugLog

from cachehash.main import Cache
from unittest.mock import patch

# Create test file
pwd = os.path.dirname(__file__)
test_file = Path(pwd, "fixtures", "bad_password.py")
test_folder = Path(pwd, "fixtures").absolute()


# Minimal configuration
config = Config()
config.runGit = False
config.runSizes = False
config.runStats = False
config.runDependencies = False
config.config["local_repos"] = [str(test_file.parent.absolute())]

# Create Cache
db_path = "semgrep.db"
db_path = Path(pwd, db_path)

test_log_path = Path(pwd, "test_log.txt")
mock_log = DebugLog(file=str(test_log_path), debug=True).log


def setup_database():
    if db_path.exists():
        os.remove(str(db_path))
    assert not db_path.exists()

    if test_log_path.exists():
        os.remove(str(test_log_path))
    assert not test_log_path.exists()


def test_cache_persistence():
    cache_path = Path(Path.home(), ".verinfast_cache/semgrep.db")

    # First run creates cache
    agent = Agent()
    agent.config.runGit = False
    agent.config.runSizes = False
    agent.config.runStats = False
    agent.config.runDependencies = False
    agent.scan()

    # Verify cache exists and has content
    assert cache_path.exists()
    assert cache_path.stat().st_size > 0


@patch("verinfast.user.__get_input__", return_value="y")
def test_semgrep_cache(self):
    setup_database()
    cache = Cache(path=db_path, table="test_cache")

    def mock_upload(*args, **kwargs):
        for k in kwargs:
            if k != "file":
                assert expected_upload[k] == kwargs[k]
            else:
                with open(kwargs[k]) as f:
                    res = json.load(f)
                    r = res["results"]
                    result = r[0]
                    assert result["extra"]["metadata"]["cwe"] is not None

    expected_upload = {"route": "findings", "source": "test"}

    # First run
    print("\nRunning first scan...")
    test_args = {
        "repo_name": "test",
        "path": test_folder,
        "config": config,
        "cache": cache,
        "upload": mock_upload,
        "template_definition": {},
        "log": mock_log,
    }
    start_time = time.time()
    run_scan(**test_args)

    first_duration = time.time() - start_time
    print(f"First scan took: {first_duration:.2f} seconds")

    # Second run should use cache
    print("\nRunning second scan...")
    second_start_time = time.time()
    run_scan(**test_args)
    second_duration = time.time() - second_start_time
    print(f"Second scan took: {second_duration:.2f} seconds")

    # Second run should be faster
    assert second_duration < (first_duration - 5)
    assert db_path.exists()
