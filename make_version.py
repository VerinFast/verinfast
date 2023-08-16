import os
import datetime


# Get the version from the git tag, and write to VERSION.
ref = None
if "GITHUB_REF" in os.environ:
    ref = os.environ["GITHUB_REF"]

if ref and ref is not None and ref.startswith("refs/tags/"):
    version = ref.replace("refs/tags/", "")
else:
    version = datetime.datetime.now().strftime("%Y.%m.%d%H%M%S")

print(version)

with open("VERSION", "w") as f:
    f.write(version)

with open("VERSION.py", "w") as f:
    f.write("__version__ = '" + str(version) + "'")
