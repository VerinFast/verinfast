import json

from verinfast.config import Config
"""
    dry
    should_upload
    base_url
    uuid
    path
    noGit
"""


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
    c.cfg_path = 'http://www.google.com'
    assert c.is_path_remote() is True
    c.cfg_path = 'https://www.google.com'
    assert c.is_path_remote() is True
    c.cfg_path = 'config.yaml'
    assert c.is_path_remote() is False
    c.cfg_path = './config.yaml'
    assert c.is_path_remote() is False
    c.cfg_path = '//config.yaml'
    assert c.is_path_remote() is False
    c.cfg_path = '/C://config.yaml'
    assert c.is_path_remote() is False


def test_config_to_json():
    c = Config()
    s = str(c)
    d = json.loads(s)
    assert d["cfg_path"] is not None
