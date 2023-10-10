import json
import os
from unittest.mock import patch
from pathlib import Path
import shutil

import pytest

from verinfast.agent import Agent
from verinfast.config import Config
from verinfast.utils.utils import DebugLog

file_path = Path(__file__)
test_folder = file_path.parent.absolute()
results_dir = test_folder.joinpath("results").absolute()


def check_children(
            i: str | dict,
            max_length=30,
            recursion_depth=0,
            excludes=["cwe", "path", "check_id"]
        ):
    if isinstance(i, str):
        if len(i) > max_length:
            print(i)
        assert len(i) <= max_length
    else:
        if isinstance(i, dict):
            for k in i:
                if k in excludes:
                    return
                try:
                    check_children(i[k], recursion_depth=recursion_depth+1)
                except Exception as e:
                    print(k)
                    raise e


@patch('verinfast.user.__get_input__', return_value='y')
def test_no_truncate(self):
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config('./str_conf.yaml')
    config.output_dir = results_dir
    agent.config = config
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        for k in r:
            with pytest.raises(AssertionError):
                check_children(k, excludes=[])


@patch('verinfast.user.__get_input__', return_value='y')
def test_truncate(self):
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config('./str_conf.yaml')
    config.output_dir = results_dir
    agent.config = config
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.config.truncate_findings = True
    agent.config.truncate_findings_length = 30
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        for k in r:
            check_children(k)


@patch('verinfast.user.__get_input__', return_value='y')
def test_truncate_from_args(self):
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config('./str_conf.yaml')
    parser = config.init_argparse()
    args = parser.parse_args(['--truncate_findings=30'])
    assert args.truncate_findings == 30
    config.handle_args(args)
    assert config.truncate_findings is True
    assert config.truncate_findings_length == 30
    config.output_dir = results_dir
    agent.config = config
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        for k in r:
            check_children(k)
