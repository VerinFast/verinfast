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


# Chunk a list
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


class DebugLog:
    def __init__(self, path: str, debug: bool = True):
        self.path = path
        self.logFile = os.path.join(path, "log.txt")
        self.debug = debug

    def log(self, msg, tag=None, display=False, timestamp=True):
        if tag is None:
            s = inspect.stack()[1]

            tag = f"{s.filename}@{s.lineno} {s.function}"
        if timestamp:
            d = date.today()
            tag = f"{d} {time.strftime('%H:%M:%S', time.localtime())} {tag}"
        output = f"{tag}: {msg}"

        with open(self.logFile, 'a') as f:
            f.write(output+"\n")
        if display or self.debug:
            print(output)
