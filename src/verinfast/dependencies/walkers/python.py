import contextlib
import io
import json
import logging
import os
import sys

from johnnydep.lib import JohnnyDist, flatten_deps

from verinfast.dependencies.walkers.classes import Walker, Entry

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

_REQUIREMENTS_FORMAT_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
}

_DEFAULT_FIELDS = [
    "name",
    "summary",
    "specifier",
    "requires",
    "required_by",
    "license",
]


def _resolve_requirements(requirement_lines, ret=True):
    """Resolve a list of PEP 508 requirement strings through JohnnyDep."""
    dists = []
    for line in requirement_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip environment markers (JohnnyDep doesn't handle them)
        if ";" in line:
            line = line.split(";")[0].strip()
        if not line:
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                dists.append(JohnnyDist(line, ignore_errors=True))
        except Exception as error:
            logger = logging.getLogger()
            logger.disabled = True
            logger.exception(error)
            logger.disabled = False

    data = []
    for d in dists:
        try:
            deps = flatten_deps(d)
            data += deps
        except Exception:
            pass

    output = [
        d for dep in data for d in dep.serialise(fields=_DEFAULT_FIELDS, recurse=False)
    ]

    dup_check = {}
    for idx, o in enumerate(output):
        k = o["name"] + o["specifier"]
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


def _parse_toml_file(filepath):
    """Read and parse a TOML file."""
    if tomllib is None:
        raise RuntimeError(
            "TOML parsing requires Python 3.11+ or the 'tomli' package. "
            "Install it with: pip install tomli"
        )
    with open(filepath, "rb") as f:
        return tomllib.load(f)


def _poetry_spec_to_pep(spec):
    """Convert Poetry version specifiers (^ and ~) to PEP 440."""
    spec = spec.strip()
    if spec.startswith("^"):
        version = spec[1:]
        parts = version.split(".")
        major = int(parts[0]) if parts else 0
        if major > 0:
            return f">={version},<{major + 1}.0.0"
        elif len(parts) > 1:
            minor = int(parts[1])
            return f">={version},<0.{minor + 1}.0"
        else:
            return f">={version},<1.0.0"
    elif spec.startswith("~"):
        version = spec[1:]
        parts = version.split(".")
        major = int(parts[0]) if parts else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        return f">={version},<{major}.{minor + 1}.0"
    else:
        return spec


def parseFile(filename="requirements.txt", ret=False):
    """Parse requirements.txt-format files (also requirements.in, requirements-dev.txt)."""
    requirement_lines = []
    with open(filename) as file:
        for line in file:
            if line.find("#") >= 0:
                line = line[0 : line.find("#")]
            stripped_line = line.rstrip()
            if stripped_line[0:2] == "--" or not stripped_line:
                pass
            else:
                requirement_lines.append(stripped_line)
    return _resolve_requirements(requirement_lines, ret=ret)


def parsePipfile(filename, ret=True):
    """Parse a Pipfile (TOML format) extracting [packages] and [dev-packages]."""
    data = _parse_toml_file(filename)
    requirement_lines = []

    for section in ("packages", "dev-packages"):
        packages = data.get(section, {})
        for name, spec in packages.items():
            if isinstance(spec, str):
                if spec == "*":
                    requirement_lines.append(name)
                else:
                    requirement_lines.append(f"{name}{spec}")
            elif isinstance(spec, dict):
                version = spec.get("version", "*")
                if version == "*":
                    requirement_lines.append(name)
                else:
                    requirement_lines.append(f"{name}{version}")

    return _resolve_requirements(requirement_lines, ret=ret)


def parsePyprojectToml(filename, ret=True):
    """Parse pyproject.toml for PEP 621 and Poetry dependencies."""
    data = _parse_toml_file(filename)
    requirement_lines = []

    # PEP 621: [project].dependencies
    project = data.get("project", {})
    deps = project.get("dependencies", [])
    requirement_lines.extend(deps)

    # PEP 621: [project].optional-dependencies
    optional = project.get("optional-dependencies", {})
    for group_deps in optional.values():
        requirement_lines.extend(group_deps)

    # Poetry: [tool.poetry.dependencies]
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        if isinstance(spec, str):
            if spec == "*":
                requirement_lines.append(name)
            else:
                requirement_lines.append(f"{name}{_poetry_spec_to_pep(spec)}")
        elif isinstance(spec, dict):
            version = spec.get("version", "*")
            if version == "*":
                requirement_lines.append(name)
            else:
                requirement_lines.append(f"{name}{_poetry_spec_to_pep(version)}")

    return _resolve_requirements(requirement_lines, ret=ret)


def parsePoetryLock(filename, ret=True):
    """Parse poetry.lock directly without JohnnyDep (versions already pinned)."""
    data = _parse_toml_file(filename)
    packages = data.get("package", [])
    output = []
    seen = set()

    for pkg in packages:
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        description = pkg.get("description", "")
        key = f"{name}=={version}"
        if key not in seen:
            seen.add(key)
            output.append(
                {
                    "name": name,
                    "specifier": f"=={version}",
                    "summary": description,
                    "license": "",
                    "requires": [],
                    "required_by": [],
                }
            )

    result = json.dumps(output, indent=2, default=str, separators=(",", ": "))
    if not ret:
        print(result)
    else:
        return output


class PyWalker(Walker):
    def parse(self, file: str, expand=False, ret=True):
        basename = os.path.basename(file)

        if basename in _REQUIREMENTS_FORMAT_FILES:
            temp = parseFile(filename=file, ret=True)
        elif basename == "Pipfile":
            temp = parsePipfile(filename=file, ret=True)
        elif basename == "pyproject.toml":
            temp = parsePyprojectToml(filename=file, ret=True)
        elif basename == "poetry.lock":
            temp = parsePoetryLock(filename=file, ret=True)
        else:
            return

        if temp is None:
            return

        for el in temp:
            el["source"] = "pip"
        self.entries.extend([Entry(**entry) for entry in temp])
