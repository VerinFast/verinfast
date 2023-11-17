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
        results = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
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
        with open(file, "r") as manifest:
            self.loggerFunc(msg=file)
            contents = manifest.read()
            self.loggerFunc(msg=contents)
            self.lines = manifest.readlines()
            do_nest = 0
            first_source = False
            sources = []
            source = None
            for line in self.lines:
                line = GemfileParser.preprocess(line)

                if line.endswith(" do"):
                    do_nest += 1
                if line.startswith("source"):
                    source = line.split()[1].replace('"', "")
                    sources.append({
                        "source": source,
                        "layer": do_nest
                    })
                    first_source = True
                if not first_source:
                    raise Exception("Invalid gemfile")
                if line == 'end':
                    do_nest -= 1
                    last_source = sources[-1]
                    if do_nest == last_source["layer"]:
                        sources.pop()
                        source = sources[-1]
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
                            dep.group = self.current_group
                            dep.parent.append(self.appname)
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
                            if dep["source"] == '':
                                dep["source"] = source
                            if dep["source"] == "https://rubygems.org":
                                self.get_license_and_children(dep["name"], dep["requirement"])
        parsed = GemfileParser(file)
        output = parsed.parse()
        runtimeDeps = output["runtime"]
        # First order dependencies
        for dep in runtimeDeps:
            license = self.get_license(dep["name"])
            e = Entry(
                        name=dep["name"],
                        specifier=" ".join(dep["requirement"]),
                        source=dep["source"],
                        license=license,
                        required_by=file
                    )
            self.entries.append(e)

        # Second order dependencies
        for dep in self.real_dependencies:
            if dep not in [n["name"] for n in runtimeDeps]:
                e = Entry(
                    name=dep,
                    specifier="=="+self.real_dependencies[dep],
                    source="gemfile child",
                    license=self.get_license(dep)
                )
                self.entries.append(e)

    def get_license(self, name: str) -> str:
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


# GET - /api/v1/versions/[GEM NAME].(json|yaml)
"""
curl https://rubygems.org/api/v1/versions/coulda.json

[
  {
    "authors" : "Evan David Light",
    "built_at" : "2011-08-08T04:00:00.000Z",
    "created_at" : "2011-08-08T21:23:40.254Z",
    "description" : "Behaviour Driven Development derived from Cucumber but as an internal DSL with methods for reuse",
    "downloads_count" : 2224,
    "number" : "0.7.1",
    "summary" : "Test::Unit-based acceptance testing DSL",
    "platform" : "ruby",
    "ruby_version" : nil,
    "prerelease" : false,
    "licenses" : nil,
    "requirements" : nil,
    "sha" : "777c3a7ed83e44198b0a624976ec99822eb6f4a44bf1513eafbc7c13997cd86c"
  }
]
"""

# GET - /api/v1/gems/[GEM NAME].(json|yaml)
"""
curl https://rubygems.org/api/v1/gems/rails.json

{
  "name": "rails",
  "downloads": 7528417,
  "version": "3.2.1",
  "version_downloads": 47602,
  "authors": "David Heinemeier Hansson",
  "info": "Ruby on Rails is a full-stack web framework optimized for programmer
          happiness and sustainable productivity. It encourages beautiful code
          by favoring convention over configuration.",
  "project_uri": "http://rubygems.org/gems/rails",
  "gem_uri": "http://rubygems.org/gems/rails-3.2.1.gem",
  "homepage_uri": "http://www.rubyonrails.org",
  "wiki_uri": "http://wiki.rubyonrails.org",
  "documentation_uri": "http://api.rubyonrails.org",
  "mailing_list_uri": "http://groups.google.com/group/rubyonrails-talk",
  "source_code_uri": "http://github.com/rails/rails",
  "bug_tracker_uri": "http://github.com/rails/rails/issues",
  "dependencies": {
    "development": [],
    "runtime": [
      {
        "name": "actionmailer",
        "requirements":"= 3.2.1"
      },
      {
        "name": "actionpack",
        "requirements": "= 3.2.1"
      },
      {
        "name": "activerecord",
        "requirements": "= 3.2.1"
      },
      {
        "name": "activeresource",
        "requirements": "= 3.2.1"
      },
      {
        "name": "activesupport",
        "requirements": "= 3.2.1"
      },
      {
        "name": "bundler",
        "requirements": "~> 1.0"
      },
      {
        "name": "railties",
        "requirements": "= 3.2.1"
      }
    ]
  }
}
"""
