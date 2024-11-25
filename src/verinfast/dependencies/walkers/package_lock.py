import json

from verinfast.dependencies.walkers.classes import Walker, Entry


class PackageWalker(Walker):
    def remote_decorate(self, entry: Entry) -> str:
        resp = None
        try:
            license_resp = self.getUrl(f"https://registry.npmjs.org/{entry.name}/{entry.specifier}/")  # NOQA:E501
            resp = json.loads(license_resp)
        except Exception as e:
            self.log(
                f"License not found for: {entry.name}@{entry.specifier}",
                display=False
            )
            self.log(e, display=False)
        if isinstance(resp, dict):
            entry.license = resp.get("license", "License not available")
            entry.summary = resp.get("description", "No description provided.")
        else:
            self.log(f"Error with {entry.name} {entry.specifier} response")
            self.log(license_resp)

    def parse(self, file: str, expand=False):
        try:
            with open(file) as f:
                d = json.load(f)
                if "dependencies" in d:
                    dependencies = d["dependencies"]
                    for dependency in dependencies:
                        try:
                            e = Entry(
                                name=dependency,
                                specifier=dependencies[dependency].get(
                                    "version", "Version not found"
                                ),
                                source="package-lock.json"
                            )
                            self.remote_decorate(entry=e)
                            self.entries.append(e)
                        except Exception as error:
                            self.log(f"error parsing {dependency}")
                            self.log(error)
                            continue
        except Exception as error:
            # handle the exception
            self.log(f"error parsing {file}")
            self.log(error)
