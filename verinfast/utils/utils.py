import os
import time

# Flag for more verbose output
debug=True

def debugLog(msg, tag='Debug Log:', display=False):
    output = f"\n{tag}:\n{msg}"
    logFile = os.path.join(os.getcwd(), "log.txt")
    output += "\n" + time.strftime("%H:%M:%S", time.localtime())
    with open(logFile, 'a') as f:
        f.write(output)
    if display or debug:
        print(output)
