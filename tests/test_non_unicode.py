from verinfast.utils.utils import std_exec


def test_std_exec():
    cmd = ["ls", "-l"]
    result = std_exec(cmd)
    assert result != ""


def test_std_exec_non_unicode():
    cmd = ["printf", b"\x80"]
    result = std_exec(cmd)
    assert result == ""
