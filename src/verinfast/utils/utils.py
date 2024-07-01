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


# Returns a dict of the repo name, repo url and branch from the original url
def get_repo_name_url_and_branch(repo_url: str):
    # The regex pattern captures the entire URL
    # and the repository name after the last '/'

    repo_url = repo_url.strip()
    branch = None

    split_url = repo_url.split("@")

    # HTTPS URLs
    if repo_url.startswith("https://") or repo_url.startswith("http://"):
        # Check for branch in URL
        if len(split_url) == 2:
            branch = split_url[1]
            repo_url = split_url[0]
        elif len(split_url) == 3:
            # Username and password in URL
            # e.g. https://user:password@my.githost.com/repo@branch
            branch = split_url[2]
            # Remove branch so that the repo name can be extracted
            # without colliding with /'s in branch name
            repo_url = repo_url.replace(f"@{branch}", "")
    else:
        # SSH URLs
        # Check for branch in URL
        if len(split_url) > 2:
            branch = split_url[2]
            # Remove branch so that the repo name can be extracted
            # without colliding with /'s in branch name
            repo_url = repo_url.replace(f"@{branch}", "")
            print(f"Repo URL after removing branch: {repo_url}")
            print(f"@{branch}")

    # Match repo_name to after the last '/' in the cleaned URL
    repo_name = repo_url.rsplit('/', 1)[-1]

    return {
        "repo_name": repo_name,
        "repo_url": repo_url,
        "branch": branch
    }
