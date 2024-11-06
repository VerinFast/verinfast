import json

from verinfast.dependencies.walkers.classes import Walker, Entry


class PackageWalker(Walker):
    def remote_decorate(self, entry: Entry) -> str:
        resp = None
        license_resp = self.getUrl(f"https://registry.npmjs.org/{entry.name}/{entry.specifier}/")  # NOQA:E501
        resp = json.loads(license_resp)
        entry.license = resp["license"]
        entry.summary = resp["description"]

    def parse(self, file: str, expand=False):
        try:
            with open(file) as f:
                d = json.load(f)
                if "dependencies" in d:
                    dependencies = d["dependencies"]
                    for dependency in dependencies:

                        e = Entry(
                            name=dependency,
                            specifier=dependencies[dependency]["version"],
                            source="package-lock.json"
                        )
                        self.remote_decorate(entry=e)
                        self.entries.append(e)

        except Exception as error:
            # handle the exception
            self.log(f"error parsing {file}")
            self.log(error)
