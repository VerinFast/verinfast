import os
import time


class DebugLog:

    def __init__(self, path, debug=True):
        self.path = path
        self.logFile = os.path.join(path, "log.txt")
        self.debug = debug

    def log(self, msg, tag, display=False):
        output = f"\n{tag}:\n{msg}"
        output += "\n" + time.strftime("%H:%M:%S", time.localtime())
        with open(self.logFile, 'a') as f:
            f.write(output)
        if display or self.debug:
            print(output)
