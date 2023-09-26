import json
import logging

from johnnydep.lib import JohnnyDist, flatten_deps

from verinfast.dependencies.walkers.classes import Walker, Entry


def parseFile(filename="requirements.txt", ret=False):
    dists = []
    default_fields = [
        "name",
        "summary",
        "specifier",
        "requires",
        "required_by",
        "license"
    ]
    with open(filename) as file:
        for line in file:
            if line.find("#") >= 0:
                line = line[0:line.find("#")]
            stripped_line = line.rstrip()
            if stripped_line[0:2] == '--' or not stripped_line:
                pass
            else:
                try:
                    dists.append(JohnnyDist(
                            stripped_line,
                            ignore_errors=True,
                        )
                    )
                except Exception as error:
                    # handle the exception, hiding for now
                    logger = logging.getLogger()
                    logger.disabled = True
                    logger.exception(error)
                    logger.disabled = False
                    pass

    data = []
    for idx, d in enumerate(dists):
        deps = flatten_deps(d)
        data += deps

    # This is the worst line of code I've ever written.
    output = [
        d for dep in data
        for d in dep.serialise(fields=default_fields, recurse=False)
    ]

    dup_check = {}
    for idx, o in enumerate(output):
        k = o["name"]+o["specifier"]
        if k in dup_check:
            output[dup_check[k]]["required_by"].append(k)
            output.remove(o)
        else:
            dup_check[k] = idx

    result = json.dumps(output, indent=2, default=str, separators=(",", ": "))
    if not ret:
        print(result)
    else:
        return output


class PyWalker(Walker):
    def parse(self, file: str, expand=False, ret=True):
        temp = parseFile(filename=file, ret=ret)
        for el in temp:
            el["source"] = "pip"
        self.entries = [Entry(**entry) for entry in temp]
