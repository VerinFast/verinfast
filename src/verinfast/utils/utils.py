from datetime import date
import inspect
import os
import time


class DebugLog:

    def __init__(self, path, debug=True):
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
