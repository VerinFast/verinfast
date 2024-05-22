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
str_path = str(test_folder.joinpath('str_conf.yaml').absolute())
results_dir = test_folder.joinpath("results").absolute()
saw_message = False
MAX_RECURSION_DEPTH = 10


def check_children(
            i: str | dict | list,
            max_length=30,
            recursion_depth=0,
            # This list must match agent.py
            excludes=[
                "cwe",
                "owasp",
                "path",
                "check_id",
                "license",
                "fingerprint",
                "message",
                "references",
                "url",
                "source",
                "severity"
            ]
        ):
    if recursion_depth > MAX_RECURSION_DEPTH:
        raise Exception("In TOO DEEP!")
    global saw_message
    # print(i)
    if isinstance(i, str):
        if len(i) > max_length:
            print(i)
        assert len(i) <= max_length
    elif isinstance(i, dict):
        for k in i:
            if k == "message":
                saw_message = True
            if k in excludes:
                print(f"{k} is excluded")
            else:
                try:
                    check_children(
                        i[k],
                        recursion_depth=recursion_depth+1,
                        excludes=excludes
                    )
                except Exception as e:
                    print(k)
                    raise e
    elif isinstance(i, list):
        for k in i:
            try:
                check_children(
                    k,
                    recursion_depth=recursion_depth+1,
                    excludes=excludes
                )
            except Exception as e:
                print(k)
                raise e
    elif (
        isinstance(i, float) or
        isinstance(i, int) or
        isinstance(i, bool)
    ):
        pass
    else:
        raise Exception("Non-serializable Object")


@patch('verinfast.user.__get_input__', return_value='y')
def test_no_truncate(self):
    global saw_message
    saw_message = False
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
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        assert r[0]["check_id"] == "bash.curl.security.curl-eval.curl-eval"
        m = r[0]["extra"]["message"]
        assert m == "Data is being eval'd from a `curl` command. An attacker with control of the server in the `curl` command could inject malicious code into the `eval`, resulting in a system comrpomise. Avoid eval'ing untrusted data if you can. If you must do this, consider checking the SHA sum of the content returned by the server to verify its integrity."  # noqa: E501
        print("CHECK CHILDREN")
        for k in r:
            with pytest.raises(AssertionError):
                check_children(
                    k,
                    excludes=[
                        "cwe",
                        "path",
                        "check_id",
                        "license",
                        "taint_sink",
                        "taint_source",
                        "fingerprint"
                    ]
                )
    assert saw_message is True


@patch('verinfast.user.__get_input__', return_value='y')
def test_truncate(self):
    global saw_message
    saw_message = False
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config(str_path)
    config.output_dir = results_dir
    assert config.runGit is True
    assert config.runScan is True
    agent.config = config
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.config.truncate_findings = True
    agent.config.truncate_findings_length = 0
    assert agent.config.runGit is True
    assert agent.config.runScan is True
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        assert r[0]["check_id"] == "bash.curl.security.curl-eval.curl-eval"
        assert r[0]["extra"]["lines"] == ""
        for k in r:
            check_children(k)
    assert saw_message is True


@patch('verinfast.user.__get_input__', return_value='y')
def test_truncate_from_args(self):
    global saw_message
    saw_message = False
    try:
        shutil.rmtree(results_dir)
    except Exception as e:
        print(e)
        pass
    os.makedirs(results_dir, exist_ok=True)
    agent = Agent()
    config = Config(str_path)
    parser = config.init_argparse()
    args = parser.parse_args(['--truncate_findings=30'])
    assert args.truncate_findings == 30
    config.handle_args(args)
    assert config.runGit is True
    assert config.runScan is True
    assert config.truncate_findings is True
    assert config.truncate_findings_length == 30
    config.output_dir = results_dir
    agent.config = config
    assert agent.config.truncate_findings is True
    assert agent.config.truncate_findings_length == 30
    agent.config.dry = False
    agent.config.shouldUpload = False
    agent.debug = DebugLog(path=agent.config.output_dir, debug=False)
    agent.log = agent.debug.log
    agent.scan()
    findings_file_path = results_dir.joinpath('small-test-repo.git.findings.json')  # NOQA: E501

    with open(findings_file_path) as f:
        d = json.load(f)
        r = d["results"]
        assert r[0]["check_id"] == "bash.curl.security.curl-eval.curl-eval"
        for k in r:
            check_children(k)
    assert saw_message is True
