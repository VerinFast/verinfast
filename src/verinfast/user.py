from pathlib import Path
import os
import yaml
from typing import List, Callable, Union


user_home = os.path.expanduser("~")


def __get_input__(t: str):
    return input(t)


def repeat_boolean_prompt(
    prompt: str, logger: Union[Callable, None] = None, default_val: bool = False
):
    valid_strs = ["y", "n"]
    print_opts = "(y/N)"
    d = "n"

    if default_val is True:
        print_opts = "(Y/n)"
        d = "y"

    logger(prompt)
    resp = repeat_prompt(prompt=print_opts, valid=valid_strs, default_val=d)

    return resp.lower() == "y"


def repeat_prompt(prompt: str, valid: List[str], default_val: Union[str, None] = None):
    prompt += "\n"
    resp = __get_input__(prompt).lower()
    while resp not in valid:
        if default_val and not resp:
            return default_val
        resp = __get_input__(prompt).lower()
    return resp


def initial_prompt():
    should_upload_log = False

    warning = """
        VerinFast™ would like to collect information about
        this scan. Do you give consent to upload diagnostic
        information to our sponsor, StartupOS at:
        https://beta.startupos.dev/
    """

    storage = f"""
        VerinFast™ stores user preferences and configurations
        in your home directory. To do that we create a hidden
        folder (.verinfast) inside the directory {user_home}.

        We never store keys, passwords or confidential information
        there. We do store consents so we don't prompt on every
        run, hashes for more efficient scanning, and other
        preferences.
    """

    f_path = Path(os.path.expanduser("~/.verinfast/")).joinpath("preferences.yaml")
    conf = {}
    if f_path.exists():
        with open(f_path, "r") as f:
            conf = yaml.safe_load(f)

    if "upload_permission" not in conf:
        resp = repeat_boolean_prompt(warning, print, True)
        if resp:
            conf["upload_permission"] = True
            should_upload_log = True
        else:
            conf["upload_permission"] = False
    else:
        should_upload_log = conf["upload_permission"]

    if "show_warning" not in conf or conf["show_warning"]:
        print(storage)
        conf["show_warning"] = False

    os.makedirs(os.path.expanduser("~/.verinfast"), exist_ok=True)

    with open(f_path, "w") as f:
        f.write(yaml.dump(conf))

    return should_upload_log


def save_path():
    return os.path.expanduser("~/.verinfast/")


if __name__ == "__main__":
    print(initial_prompt())
