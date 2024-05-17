import csv
import io
import json
import subprocess

# from pathlib import Path
# from typing import List

# Important notes: Ruby will install at most one version of a gem, and will fail if versions conflict.


from gemfileparser import GemfileParser, Dependency

from verinfast.dependencies.walkers.classes import Walker, Entry


class GemWalker(Walker):
    def parse(self, file: str, expand=False):
        command = f"gem install -r --explain --no-user-install --install-dir gems -g {file}"
        try:
            results = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.loggerFunc(msg=f'gem install results: {results.stderr.decode()}')

            log = results.stdout.decode()
            self.real_dependencies = {}
            for line in log.splitlines():
                line = line.strip()
                if line == "Gems to install:":
                    pass
                else:
                    split_position = line.rindex('-')
                    gem_name = line[0:split_position]
                    gem_version = line[split_position+1:]
                    self.real_dependencies[gem_name] = gem_version
        except:  # noqa:E722
            self.loggerFunc(msg=f"Failed to parse Gemfile {file}", display=True)
            with open(file, "r") as manifest:
                self.loggerFunc(msg=file)
                contents = manifest.read()
                self.loggerFunc(msg=contents+"\n\n\n")
            return

        # Yes this is necessary
        with open(file, "r") as manifest:
            self.lines = manifest.readlines()
            do_nest = 0
            first_source = False
            sources = []
            source = None
            deps = []
            for line in self.lines:
                line = GemfileParser.preprocess(line)
                if len(line) > 0:
                    if line.endswith(" do"):
                        do_nest += 1
                    if line.startswith("source"):
                        source = line.split()[1].replace('"', "").replace("'", "")
                        sources.append({
                            "source": source,
                            "layer": do_nest
                        })
                        first_source = True
                    if not first_source and not line.startswith("ruby"):
                        self.loggerFunc(msg=manifest.read() + '\n\n\n')
                        self.loggerFunc(msg=f"Invalid gemfile {file}")
                        return
                    if line == 'end':
                        if len(sources) == 0:
                            self.loggerFunc(msg=manifest.read() + '\n\n\n')
                            self.loggerFunc(msg=f"Invalid gemfile {file}")
                            return
                        last_source = sources[-1]
                        if do_nest == last_source["layer"]:
                            sources.pop()
                            if len(sources) > 0:
                                source = sources[-1]["source"]
                            else:
                                source = None
                        do_nest -= 1

                    if line.startswith("gem"):
                        linefile = io.StringIO(line)
                        for line2 in csv.reader(linefile, delimiter=","):
                            column_list = []
                            for column in line2:
                                stripped_column = (
                                    column.replace("'", "")
                                    .replace('"', "")
                                    .replace("%q<", "")
                                    .replace("(", "")
                                    .replace(")", "")
                                    .replace("[", "")
                                    .replace("]", "")
                                    .replace(".freeze", "")
                                    .strip()
                                )
                                column_list.append(stripped_column)

                                dep = Dependency()
                                # dep.group = self.current_group
                                # dep.parent.append(self.appname)
                                for column in column_list:
                                    # Check for a match in each regex and assign to
                                    # corresponding variables
                                    for criteria, criteria_regex in GemfileParser.gemfile_regexes.items():
                                        match = criteria_regex.match(column)
                                        if match:
                                            if criteria == "requirement":
                                                dep.requirement.append(match.group(criteria))
                                            else:
                                                setattr(dep, criteria, match.group(criteria))
                                            break
                                if dep.name.startswith("gem "):
                                    dep.name = dep.name[4:].strip()
                                if not dep.requirement:
                                    dep.requirement.append("*")
                                if dep.source == '' or dep.source is None:
                                    dep.source = source
                                if dep.source == '' or dep.source is None:
                                    dep.source = "https://rubygems.org"
                                if dep.source == "https://rubygems.org":
                                    self.get_license(dep.name)
                                deps.append(dep)
                    else:
                        pass

        for dep in deps:
            license = self.get_license(getattr(dep, "name"))
            e = Entry(
                        name=dep.name,
                        specifier=" ".join(dep.requirement),
                        source=dep.source,
                        license=license,
                        required_by=file
                    )
            self.entries.append(e)

        # Second order dependencies
        for dep in self.real_dependencies:
            if dep not in [n.name for n in deps]:
                e = Entry(
                    name=dep,
                    specifier="=="+self.real_dependencies[dep],
                    source="gemfile child",
                    license=self.get_license(dep)
                )
                self.entries.append(e)

    def get_license(self, name: str) -> str:
        if name not in self.real_dependencies:
            return ""
        version = self.real_dependencies[name]
        license = ""
        try:
            resp = self.getUrl(f'https://rubygems.org/api/v2/rubygems/{name}/versions/{version}.json')
            resp = json.loads(resp)
            license = " ".join(resp["licenses"]) if resp["licenses"] is not None else ""
        except Exception as e2:
            self.log(
                f"License not found for: {name}@{version}",
                display=False
            )
            self.log(e2, display=False)
        return license

    def expand(self, file):
        raise Exception("No expansion for this Walker")
