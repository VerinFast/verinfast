import json
from pathlib import Path

from verinfast.config import Config
"""
    dry
    should_upload
    base_url
    uuid
    path
    noGit
"""

file_path = Path(__file__)
test_folder = file_path.parent.absolute()


def test_arg_dry():
    c = Config()
    parser = c.init_argparse()
    args = parser.parse_args(['--dry'])
    assert args.dry is True
    c.handle_args(args)
    assert c.dry is True


def test_arg_should_upload():
    c = Config()
    parser = c.init_argparse()
    args = parser.parse_args(['--should_upload'])
    assert args.should_upload is True
    c.handle_args(args)
    assert c.shouldUpload is True


def test_is_remote():
    c = Config()
    c.original_cfg_path = 'http://www.google.com'
    assert c.is_original_path_remote() is True
    c.original_cfg_path = 'https://www.google.com'
    assert c.is_original_path_remote() is True
    c.original_cfg_path = 'config.yaml'
    assert c.is_original_path_remote() is False
    c.original_cfg_path = './config.yaml'
    assert c.is_original_path_remote() is False
    c.original_cfg_path = '//config.yaml'
    assert c.is_original_path_remote() is False
    c.original_cfg_path = '/C://config.yaml'
    assert c.is_original_path_remote() is False


def test_config_to_json():
    c = Config()
    s = str(c)
    d = json.loads(s)
    assert d["cfg_path"] is not None


def test_should_git_with_args():
    conf_path = test_folder.joinpath('str_conf.yaml').absolute()
    config = Config(str(conf_path))
    parser = config.init_argparse()
    args = parser.parse_args(['--truncate_findings=30'])
    assert args.truncate_findings == 30
    config.handle_args(args)
    assert config.runGit is True


def test_should_git_with_args_set():
    config = Config()
    parser = config.init_argparse()
    args = parser.parse_args(['-g'])
    assert args.should_git is True
    config.handle_args(args)
    assert config.runGit is True
