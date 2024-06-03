from datetime import date
import inspect
import os
import re
from glob import glob
import subprocess
import time

from typing import List

STD_EXCLUDE_LIST = [
                "**/.git/**",
                "**/node_modules/**",
                "build/**",
                "dist/**",
                "env/**",
                "venv/**",
                "**/__pycache__/**",
                "**/*.pyc",
                "**/*.pyo",
                "**/*.log",
                "**/*.swp",
                "**/*.swo",
                "**/*.DS_Store",
                "**/.idea/**"
            ]


"""
newline = "\n" #
TODO - Set to system appropriate newline character.
This doesn't work with modernmetric
"""


def list_files(
        path: str,
        incl: List[glob] = ["*.*"],
        excl: List[glob] = STD_EXCLUDE_LIST
        ):
    files = []
    excluded = []
    for i in incl:
        files += glob(os.path.join(path, i))
    for e in excl:
        excluded += glob(os.path.join(path, e))
    files = [f for f in files if f not in excluded]
    return files


def std_exec(cmd: List[str]):
    return subprocess.check_output(cmd).decode('utf-8')


def escapeChars(text: str):
    fixedText = re.sub(r'([\"\{\}])', r'\\\1', text)
    return fixedText


def trimLineBreaks(text: str):
    return text.replace("\n", "").replace("\r", "")


# Truncate large strings for display
def truncate(text, length=100):
    testStr = str(text)  # Supports passing in Lists and other types
    return ((testStr[:length] + '..') if len(testStr) > length else testStr)


def truncate_children(
            obj: dict | list,
            log,
            excludes=[],
            max_length=30,
            recursion_depth=0
        ):
    if isinstance(obj, dict):
        for k in obj:
            v = obj[k]
            if k in excludes:
                pass
            elif isinstance(v, str):
                obj[k] = v[0:max_length]
            elif (
                isinstance(v, int) or
                isinstance(v, float) or
                isinstance(v, bool)
            ):
                pass
            else:
                obj[k] = truncate_children(
                    obj[k],
                    log,
                    excludes=excludes,
                    max_length=max_length,
                    recursion_depth=recursion_depth + 1
                )
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                obj[i] = v[0:max_length]
            elif (
                isinstance(v, int) or
                isinstance(v, float) or
                isinstance(v, bool)
            ):
                pass
            else:
                obj[i] = truncate_children(
                    obj[i],
                    log,
                    excludes=excludes,
                    max_length=max_length,
                    recursion_depth=recursion_depth + 1
                )

    return obj


# Chunk a list
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


class DebugLog:
    def __init__(self, path: str, debug: bool = False):
        self.path = path
        self.logFile = os.path.join(path, "log.txt")
        self.debug = debug

    def log(self, msg, tag=None, display=False, timestamp=True):
        if tag is None and timestamp:
            s = inspect.stack()[1]

            tag = f"{s.filename}@{s.lineno} {s.function}"
        if timestamp:
            d = date.today()
            tag = f"{d} {time.strftime('%H:%M:%S', time.localtime())} {tag}"
        if tag != "":
            output = f"{tag}: {msg}"
        else:
            output = f"{msg}"

        with open(self.logFile, 'a') as f:
            f.write(output+"\n")
        if display or self.debug:
            print(output)


# Returns a tuple of the repo name and the repo url from the original url
def get_repo_name_url_and_branch(repo_url: str):
    # match = re.search(r"([^/]*\.git.*)", repo_url) ^.*?/(.*)
    # The regex pattern captures the entire URL
    # and the repository name after the last '/'
    # match = re.search(r"([^/]*\.git.*)", repo_url) # Old regex

    branch = None
    # Match repo_name to after the last '/' in the URL
    match = re.search(r"(^[^@]*/(.*))", repo_url)
    if match:
        repo_name = match.group(2)
    else:
        repo_name = repo_url.rsplit('/', 1)[-1]
    # Handle an @ in the middle of the URL, e.g.
    # git@github.com:StartupOS/small-test-repo.git@develop
    if "@" in repo_name and re.search(r"^.*@.*\..*:", repo_url):
        repo_url = "@".join(repo_url.split("@")[0:2])
    elif "@" in repo_name:
        # Remove branch from url
        repo_url = repo_url.split("@")[0]
    if "@" in repo_name:
        split_repo_name = repo_name.split("@")
        branch = split_repo_name[1]
        repo_name = split_repo_name[0]
    return repo_name, repo_url, branch
