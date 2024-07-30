from verinfast.dependencies.walkers.classes import Walker, Entry


class GoWalker(Walker):
    def parse(self, file: str, expand=False):
        with open(file, "r") as file:
            for line in file:
                name, version, hash_string = line.split(" ")
                if version.endswith("go.mod"):
                    version = version.split("/")[0]
                e = Entry(
                    name=name,
                    specifier=version,
                    source="Go"
                )
                self.entries.append(e)
