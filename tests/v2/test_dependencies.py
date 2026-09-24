"""The nine-ecosystem dependency inventory.

Parsers are pure functions over strings, so most of this is offline by
construction. The registry client is exercised through `httpx.MockTransport`;
nothing here opens a socket (`N16`).
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from verinfast2 import ScanConfig, Scanner
from verinfast2.core.context import scan_context
from verinfast2.dependencies.models import Entry
from verinfast2.dependencies.parsers import (
    MANIFESTS,
    container,
    dotnet,
    golang,
    javascript,
    jvm,
    parser_for,
    php,
    python,
    ruby,
)
from verinfast2.dependencies.registry import RegistryClient, _pick
from verinfast2.dependencies.walk import (
    Discovery,
    Walk,
    deduplicate,
    discover,
    preferred,
)
from verinfast2.models import Artifact, Outcome, ScanTarget
from verinfast2.scanners.dependencies import DependencyScanner


def offline() -> RegistryClient:
    """A registry that is guaranteed not to reach the network."""
    return RegistryClient(enabled=False)


@pytest.fixture
def ctx_for():
    made = []

    def build(config: ScanConfig | None = None):
        manager = scan_context(config or ScanConfig(), log=logging.getLogger("test"))
        ctx = manager.__enter__()
        made.append(manager)
        return ctx

    yield build
    for manager in made:
        manager.__exit__(None, None, None)


def names(entries: list[Entry]) -> list[str]:
    return [entry.name for entry in entries]


def spec_of(entries: list[Entry], name: str) -> str | None:
    return next(e.specifier for e in entries if e.name == name)


# -- The Entry model --------------------------------------------------------


def test_an_entry_needs_a_name_and_a_source():
    with pytest.raises(ValueError):
        Entry(name="", source="pypi")
    with pytest.raises(ValueError):
        Entry(name="requests", source="  ")


def test_empty_optional_fields_are_omitted_from_the_payload():
    """ATD distinguishes an absent key from an empty one, and v1 wrote the
    literal string "License not available" into the licence column."""
    payload = Entry(name="requests", source="pypi").payload()

    assert payload == {"name": "requests", "source": "pypi"}


def test_pick_drops_blank_values():
    assert _pick(license="MIT", summary="") == {"license": "MIT"}
    assert _pick(license=None) == {}


# -- Go ---------------------------------------------------------------------


def test_go_collapses_the_go_mod_line():
    """go.sum has two lines per module; they are one dependency."""
    text = "example.com/m v1.2.3 h1:aaa=\n" "example.com/m v1.2.3/go.mod h1:bbb=\n"
    entries = golang.parse(text, "go.sum")

    assert [(e.name, e.specifier) for e in entries] == [("example.com/m", "v1.2.3")]


def test_go_survives_a_trailing_newline():
    """v1 did `name, version, hash = line.split(" ")`, which raises on a
    blank line — and go.sum ends with one, so it raised on every file."""
    assert golang.parse("example.com/m v1.0.0 h1:x=\n\n", "go.sum")


def test_go_ignores_a_malformed_line():
    assert golang.parse("garbage\nexample.com/m v1.0.0 h1:x=\n", "go.sum")


# -- Maven ------------------------------------------------------------------

POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties><springVersion>5.3.0</springVersion></properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${springVersion}</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
    </dependency>
  </dependencies>
</project>
"""


def test_maven_finds_dependencies_in_a_namespaced_pom():
    """Maven namespaces every element. v1 searched a bare
    `dependencies/dependency` path, which matches nothing in a real pom —
    so its Maven walker silently found nothing on most projects."""
    entries = jvm.parse(POM, "pom.xml")

    assert names(entries) == ["org.springframework/spring-core", "junit/junit"]


def test_maven_resolves_a_property_reference():
    """v1 emitted the literal `==${springVersion}`."""
    entries = jvm.parse(POM, "pom.xml")

    assert spec_of(entries, "org.springframework/spring-core") == "==5.3.0"


def test_maven_omits_a_version_it_cannot_resolve():
    """One inherited from a parent pom. Better absent than a literal `${}`."""
    pom = POM.replace(
        "<properties><springVersion>5.3.0</springVersion></properties>", ""
    )
    entries = jvm.parse(pom, "pom.xml")

    assert spec_of(entries, "org.springframework/spring-core") is None


def test_a_malformed_pom_yields_nothing_rather_than_raising():
    assert jvm.parse("<project><unclosed>", "pom.xml") == []


# -- NuGet ------------------------------------------------------------------


def test_csproj_reads_the_version_attribute():
    text = """<Project><ItemGroup>
      <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" />
    </ItemGroup></Project>"""
    entries = dotnet.parse(text, "App.csproj")

    assert [(e.name, e.specifier) for e in entries] == [
        ("Swashbuckle.AspNetCore", "==6.5.0")
    ]


def test_csproj_also_reads_the_version_child_element():
    """v1 read only the attribute and raised a KeyError on this form."""
    text = """<Project><ItemGroup>
      <PackageReference Include="Newtonsoft.Json"><Version>13.0.1</Version></PackageReference>
    </ItemGroup></Project>"""
    entries = dotnet.parse(text, "App.csproj")

    assert spec_of(entries, "Newtonsoft.Json") == "==13.0.1"


#: What a legacy (non-SDK-style) MSBuild project declares. An SDK-style one
#: declares nothing, which is why the bare path looked correct.
MSBUILD_NS = "http://schemas.microsoft.com/developer/msbuild/2003"


@pytest.mark.parametrize("extra", ["", ' ToolsVersion="15.0"'])
def test_a_namespaced_csproj_is_read_like_a_pom(extra: str):
    """A legacy MSBuild project declares a default namespace, so every element
    is `{that}PackageReference`. A bare path matched none of them and the
    project reported no .NET dependencies at all — "found nothing" and "never
    ran" made to look alike (`F18`)."""
    text = f"""<Project xmlns="{MSBUILD_NS}"{extra}><ItemGroup>
      <PackageReference Include="Serilog" Version="3.1.1" />
    </ItemGroup></Project>"""
    entries = dotnet.parse(text, "Legacy.csproj")

    assert [(e.name, e.specifier) for e in entries] == [("Serilog", "==3.1.1")]


def test_a_namespaced_csproj_also_reads_the_version_child_element():
    """The child lookup is namespaced too, and missing it loses the version
    rather than the whole entry — the quieter half of the same bug."""
    text = f"""<Project xmlns="{MSBUILD_NS}"><ItemGroup>
      <PackageReference Include="Newtonsoft.Json">
        <Version>13.0.1</Version>
      </PackageReference>
    </ItemGroup></Project>"""
    entries = dotnet.parse(text, "Legacy.csproj")

    assert spec_of(entries, "Newtonsoft.Json") == "==13.0.1"


def test_csproj_is_matched_by_suffix():
    assert parser_for("Some.Project.csproj") is dotnet.parse


# -- Containers -------------------------------------------------------------


@pytest.mark.parametrize(
    "address,expected",
    [
        ("python:3.11", ("python", "3.11")),
        ("python", ("python", "*")),
        ("python@sha256:abc", ("python", "sha256:abc")),
        ("library/python:3.11", ("library/python", "3.11")),
        # The colon before a registry port looks exactly like the one before
        # a tag, which is why the split is anchored on the last slash.
        (
            "registry.example.com:5000/team/app",
            ("registry.example.com:5000/team/app", "*"),
        ),
        (
            "registry.example.com:5000/team/app:1.2",
            ("registry.example.com:5000/team/app", "1.2"),
        ),
    ],
)
def test_image_addresses_split_correctly(address: str, expected: tuple[str, str]):
    assert container.split_address(address) == expected


def test_a_multistage_dockerfile_does_not_report_the_stage_name():
    entries = container.parse("FROM python:3.11 AS builder\n", "Dockerfile")

    assert [(e.name, e.specifier) for e in entries] == [("python", "3.11")]


def test_compose_images_are_reported_with_their_own_source():
    entries = container.parse('services:\n  web:\n    image: "nginx:1.25"\n', "c.yml")

    assert entries[0].source == "docker-compose"
    assert entries[0].name == "nginx"


def test_an_interpolated_image_is_skipped():
    """`image: ${REGISTRY}/app` names nothing we can resolve."""
    assert container.parse("    image: ${REGISTRY}/app\n", "c.yml") == []


# -- JavaScript -------------------------------------------------------------


def test_package_json_reports_what_the_project_declares():
    """v1 parsed installed packages' own manifests, so it reported each
    package rather than what the scanned project depends on."""
    text = '{"name": "app", "version": "1.0.0", "dependencies": {"lodash": "^4.17.0"}}'
    entries = javascript.parse_package_json(text, "package.json")

    assert [(e.name, e.specifier) for e in entries] == [("lodash", "^4.17.0")]
    assert "app" not in names(entries)


def test_a_bare_version_becomes_an_exact_pin():
    text = '{"dependencies": {"left-pad": "1.3.0"}}'
    assert javascript.parse_package_json(text, "p")[0].specifier == "==1.3.0"


def test_package_lock_v3_is_read():
    """v1 read only the `dependencies` map, which lockfile v3 drops — so a
    modern lockfile produced nothing at all."""
    text = """{
      "lockfileVersion": 3,
      "packages": {
        "": {"name": "app"},
        "node_modules/lodash": {"version": "4.17.21", "license": "MIT"}
      }
    }"""
    entries = javascript.parse_package_lock(text, "package-lock.json")

    assert [(e.name, e.specifier, e.license) for e in entries] == [
        ("lodash", "4.17.21", "MIT")
    ]


def test_package_lock_v1_is_still_read():
    text = '{"lockfileVersion": 1, "dependencies": {"lodash": {"version": "4.17.21"}}}'
    assert names(javascript.parse_package_lock(text, "p")) == ["lodash"]


def test_a_lockfile_listing_a_package_twice_reports_it_once():
    text = """{
      "packages": {"node_modules/a": {"version": "1.0.0"}},
      "dependencies": {"a": {"version": "1.0.0"}}
    }"""
    assert len(javascript.parse_package_lock(text, "p")) == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        ('"MIT"', "MIT"),
        ('{"type": "MIT"}', "MIT"),
        ('[{"type": "MIT"}, {"type": "Apache-2.0"}]', "MIT Apache-2.0"),
    ],
)
def test_npm_license_shapes(value: str, expected: str):
    text = (
        '{"packages": {"node_modules/a": {"version": "1.0.0", "license": %s}}}' % value
    )

    assert javascript.parse_package_lock(text, "p")[0].license == expected


# -- Python -----------------------------------------------------------------


def test_requirements_strips_comments_markers_and_options():
    text = (
        "requests==2.31.0  # pinned\n"
        "-r other.txt\n"
        "--index-url https://example.invalid\n"
        'flask>=3.0 ; python_version > "3.9"\n'
        "\n"
    )
    entries = python.parse_requirements(text, "requirements.txt")

    assert [(e.name, e.specifier) for e in entries] == [
        ("requests", "==2.31.0"),
        ("flask", ">=3.0"),
    ]


def test_requirements_ignores_a_url_or_path_requirement():
    text = "https://example.invalid/pkg.whl\n./local-package\nrequests\n"

    assert names(python.parse_requirements(text, "r.txt")) == ["requests"]


def test_extras_do_not_become_part_of_the_name():
    entries = python.parse_requirements("httpx[http2]>=0.28\n", "r.txt")

    assert entries[0].name == "httpx"


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("^1.2.3", ">=1.2.3,<2.0.0"),
        # Below 1.0 the minor version plays the major's role, so this pins
        # far more tightly than it looks.
        ("^0.2.3", ">=0.2.3,<0.3.0"),
        ("^0.0.3", ">=0.0.3,<0.1.0"),
        ("~1.2", ">=1.2,<1.3.0"),
        (">=1.0", ">=1.0"),
    ],
)
def test_poetry_specifiers_convert_to_pep_440(spec: str, expected: str):
    assert python.poetry_specifier(spec) == expected


def test_pyproject_reads_pep_621_and_poetry_and_skips_python_itself():
    text = """
[project]
dependencies = ["httpx>=0.28"]
[project.optional-dependencies]
dev = ["pytest"]
[tool.poetry.dependencies]
python = "^3.11"
rich = "^13.0"
"""
    entries = python.parse_pyproject(text, "pyproject.toml")

    assert names(entries) == ["httpx", "pytest", "rich"]


def test_poetry_lock_pins_exactly():
    text = '[[package]]\nname = "requests"\nversion = "2.31.0"\ndescription = "HTTP"\n'
    entries = python.parse_poetry_lock(text, "poetry.lock")

    assert (entries[0].specifier, entries[0].summary) == ("==2.31.0", "HTTP")


def test_malformed_toml_yields_nothing_rather_than_raising():
    assert python.parse_pyproject("[project\nbroken", "pyproject.toml") == []


# -- Ruby -------------------------------------------------------------------


def test_gemfile_keeps_hyphenated_names_intact():
    """v1 split the `gem install --explain` output on the *last hyphen* to
    separate name from version, which mangles every gem with one in its
    name."""
    entries = ruby.parse_gemfile('gem "rspec-core", "~> 3.12"\n', "Gemfile")

    assert [(e.name, e.specifier) for e in entries] == [("rspec-core", "~> 3.12")]


def test_gemfile_keyword_options_are_not_read_as_versions():
    entries = ruby.parse_gemfile('gem "rails", require: false\n', "Gemfile")

    assert entries[0].specifier is None


def test_gemfile_lock_reports_resolved_versions():
    text = """GEM
  remote: https://rubygems.org/
  specs:
    rspec-core (3.12.0)
      rspec-support (~> 3.12.0)
    rails (7.0.4)

PLATFORMS
  ruby
"""
    entries = ruby.parse_gemfile_lock(text, "Gemfile.lock")

    assert [(e.name, e.specifier) for e in entries] == [
        ("rspec-core", "==3.12.0"),
        ("rails", "==7.0.4"),
    ]


def test_a_nested_dependency_line_is_not_a_top_level_gem():
    """Indentation is the only thing distinguishing them."""
    entries = ruby.parse_gemfile_lock(
        "  specs:\n    rails (7.0.4)\n      actionpack (= 7.0.4)\n", "Gemfile.lock"
    )

    assert names(entries) == ["rails"]


# -- Composer ---------------------------------------------------------------


def test_composer_skips_platform_requirements():
    text = '{"require": {"php": ">=8.1", "ext-json": "*", "monolog/monolog": "^3.0"}}'
    entries = php.parse(text, "composer.json")

    assert names(entries) == ["monolog/monolog"]


# -- Discovery --------------------------------------------------------------


def write(root: Path, rel: str, text: str = "{}") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_one_traversal_finds_every_ecosystem(tmp_path: Path):
    for rel in ("package.json", "api/pom.xml", "svc/go.sum", "web/Dockerfile"):
        write(tmp_path, rel)

    found = discover(tmp_path, [])

    assert sorted(item.name for item in found) == [
        "Dockerfile",
        "go.sum",
        "package.json",
        "pom.xml",
    ]


def test_discovery_never_descends_into_node_modules(tmp_path: Path):
    """Walking a dependency's own vendored tree costs more than the rest of
    the scan and reports the wrong thing."""
    write(tmp_path, "package.json")
    write(tmp_path, "node_modules/left-pad/package.json")

    found = discover(tmp_path, [])

    assert [item.rel for item in found] == ["package.json"]


def test_discovered_paths_are_relative_to_the_scan_root(tmp_path: Path):
    """An absolute path leaks the scanning machine's layout (`S3`)."""
    write(tmp_path, "api/pom.xml")

    assert discover(tmp_path, [])[0].rel == "api/pom.xml"


def test_a_lockfile_supersedes_its_manifest_in_the_same_directory():
    found = [
        Discovery(path=Path("/x/pyproject.toml"), rel="pyproject.toml"),
        Discovery(path=Path("/x/poetry.lock"), rel="poetry.lock"),
    ]

    assert [item.name for item in preferred(found)] == ["poetry.lock"]


def test_the_preference_is_per_directory():
    """A monorepo's packages each have their own lockfile — or don't."""
    found = [
        Discovery(path=Path("/x/a/package.json"), rel="a/package.json"),
        Discovery(path=Path("/x/a/package-lock.json"), rel="a/package-lock.json"),
        Discovery(path=Path("/x/b/package.json"), rel="b/package.json"),
    ]

    assert [item.rel for item in preferred(found)] == [
        "a/package-lock.json",
        "b/package.json",
    ]


def test_deduplicate_merges_what_each_copy_knows():
    merged = deduplicate(
        [
            Entry(name="a", source="npm", specifier="1.0.0"),
            Entry(name="a", source="npm", specifier="1.0.0", license="MIT"),
        ]
    )

    assert len(merged) == 1
    assert merged[0].license == "MIT"


def test_deduplicate_keeps_different_versions_apart():
    merged = deduplicate(
        [
            Entry(name="a", source="npm", specifier="1.0.0"),
            Entry(name="a", source="npm", specifier="2.0.0"),
        ]
    )

    assert len(merged) == 2


# -- The registry client ----------------------------------------------------


def client_for(handler, **kwargs) -> RegistryClient:
    return RegistryClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs
    )


def test_npm_lookup_returns_licence_and_summary():
    def handler(request):
        return httpx.Response(200, json={"license": "MIT", "description": "A lib"})

    assert client_for(handler).npm("lodash", "4.17.21") == {
        "license": "MIT",
        "summary": "A lib",
    }


def test_a_disabled_client_makes_no_request():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={})

    assert client_for(handler, enabled=False).npm("lodash", "4.17.21") == {}
    assert calls["n"] == 0


def test_a_failed_lookup_leaves_the_field_unset_rather_than_inventing_one():
    """v1 wrote "License not available" into the licence column, so ATD
    stores that string as though it were a licence."""

    def handler(request):
        return httpx.Response(404)

    assert client_for(handler).npm("nope", "1.0.0") == {}


def test_a_timeout_is_not_fatal():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    assert client_for(handler).pypi("requests", "2.31.0") == {}


def test_a_dead_registry_is_abandoned_after_the_failure_budget():
    """There is one request per dependency. Paying a 10-second timeout on
    each of 400 packages is an hour of scan time for nothing."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("refused", request=request)

    client = client_for(handler, failure_budget=3)
    for index in range(20):
        client.npm(f"pkg{index}", "1.0.0")

    assert calls["n"] == 3


def test_a_404_does_not_count_against_the_connectivity_budget():
    """A missing package is a real answer, not a network problem."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    client = client_for(handler, failure_budget=2)
    for index in range(5):
        client.npm(f"pkg{index}", "1.0.0")

    assert calls["n"] == 5


def test_repeated_lookups_of_one_package_hit_the_network_once():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"license": "MIT"})

    client = client_for(handler)
    client.npm("lodash", "4.17.21")
    client.npm("lodash", "4.17.21")

    assert calls["n"] == 1


def test_specifiers_are_cleaned_before_being_put_in_a_url():
    seen: list[str] = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"license": "MIT"})

    client_for(handler).npm("lodash", "==4.17.21")

    assert seen[0].endswith("/lodash/4.17.21")


def test_an_injected_client_is_not_closed():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    registry = RegistryClient(client=client)

    registry.close()

    assert not client.is_closed


# -- Enrichment -------------------------------------------------------------


def test_enrichment_only_fills_gaps():
    """A lockfile records what was actually installed; the registry records
    what is published now. Prefer the lockfile."""

    def handler(request):
        return httpx.Response(200, json={"license": "Apache-2.0", "description": "x"})

    entries = [Entry(name="a", source="npm", specifier="1.0.0", license="MIT")]
    Walk(registry=client_for(handler)).enrich(entries)

    assert entries[0].license == "MIT"
    assert entries[0].summary == "x"


def test_enrichment_is_skipped_entirely_when_disabled():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"license": "MIT"})

    entries = [Entry(name="a", source="npm", specifier="1.0.0")]
    Walk(registry=client_for(handler, enabled=False)).enrich(entries)

    assert calls["n"] == 0
    assert entries[0].license is None


def test_an_ecosystem_with_no_registry_is_left_alone():
    """Docker images and Maven artifacts have no lookup wired."""
    entries = [Entry(name="python", source="Dockerfile", specifier="3.11")]
    Walk(registry=offline()).enrich(entries)

    assert entries[0].license is None


# -- The scanner ------------------------------------------------------------


def test_the_scanner_produces_atds_flat_array(tmp_path: Path, ctx_for):
    write(tmp_path, "package.json", '{"dependencies": {"lodash": "^4.17.0"}}')
    write(tmp_path, "go.sum", "example.com/m v1.0.0 h1:x=\n")

    result = DependencyScanner(registry=offline()).run(
        ctx_for(), ScanTarget(name="app", path=tmp_path)
    )

    assert result.outcome is Outcome.OK
    assert isinstance(result.data, list)
    assert all({"name", "source"} <= set(row) for row in result.data)
    assert {row["name"] for row in result.data} == {"lodash", "example.com/m"}


def test_a_tree_with_no_manifests_is_a_skip_with_a_reason(tmp_path: Path, ctx_for):
    """Distinguishable from a project that genuinely has none (`F18`)."""
    (tmp_path / "code.py").write_text("x = 1\n")

    result = DependencyScanner(registry=offline()).run(
        ctx_for(), ScanTarget(name="app", path=tmp_path)
    )

    assert result.outcome is Outcome.SKIPPED
    assert "no dependency manifests" in result.error


def test_one_unparseable_manifest_does_not_lose_the_others(tmp_path: Path, ctx_for):
    write(tmp_path, "pom.xml", "<project><unclosed>")
    write(tmp_path, "go.sum", "example.com/m v1.0.0 h1:x=\n")

    result = DependencyScanner(registry=offline()).run(
        ctx_for(), ScanTarget(name="app", path=tmp_path)
    )

    assert result.outcome is Outcome.OK
    assert names([Entry(**row) for row in result.data]) == ["example.com/m"]


def test_the_scanner_never_runs_a_package_manager(tmp_path: Path, ctx_for, monkeypatch):
    """v1 ran `npm install`, `composer install` and `gem install` against the
    scanned project, executing arbitrary code from its dependency graph
    (`S7`, `S8`)."""
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError(f"a subprocess was started: {args!r}")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "call", forbidden)
    monkeypatch.setattr(subprocess, "check_call", forbidden)
    write(tmp_path, "package.json", '{"dependencies": {"lodash": "^4.17.0"}}')
    write(tmp_path, "composer.json", '{"require": {"monolog/monolog": "^3.0"}}')
    write(tmp_path, "Gemfile", 'gem "rails"\n')

    result = DependencyScanner(registry=offline()).run(
        ctx_for(), ScanTarget(name="app", path=tmp_path)
    )

    assert result.outcome is Outcome.OK


def test_the_scanner_is_wired_into_a_full_scan(tmp_path: Path):
    config = ScanConfig(
        targets=[ScanTarget(name="app", path=tmp_path)],
        privacy={"enrich_dependencies": False},
        write_files=False,
    )
    write(tmp_path, "go.sum", "example.com/m v1.0.0 h1:x=\n")

    result = Scanner(config).scan()
    deps = result.of(Artifact.DEPENDENCIES)[0]

    assert deps.outcome is Outcome.OK
    assert deps.data[0]["name"] == "example.com/m"


def test_every_manifest_in_the_table_resolves_to_a_parser():
    for filename in MANIFESTS:
        assert parser_for(filename) is not None


# -- Findings from review ---------------------------------------------------


@pytest.mark.parametrize(
    "line,expected",
    [
        ("FROM --platform=linux/amd64 python:3.11", ("python", "3.11")),
        ("FROM --platform=$BUILDPLATFORM node:20 AS build", ("node", "20")),
        ("FROM python:3.11", ("python", "3.11")),
    ],
)
def test_from_options_are_not_mistaken_for_the_image(line: str, expected):
    """`FROM --platform=...` is valid Docker. Taking the first token made
    the option itself the dependency name."""
    entries = container.parse(line + "\n", "Dockerfile")

    assert [(e.name, e.specifier) for e in entries] == [expected]


def test_a_from_line_with_only_options_is_skipped():
    assert container.parse("FROM --platform=linux/amd64\n", "Dockerfile") == []


def test_a_real_answer_clears_a_run_of_connectivity_failures():
    """A 404 means the package is not there — a working registry. Leaving
    the failure count standing let a few transient errors plus some missing
    packages abandon a registry that was fine."""
    answers = [None, None, 404, None, None, 200]

    def handler(request):
        outcome = answers.pop(0)
        if outcome is None:
            raise httpx.ConnectError("refused", request=request)
        if outcome == 200:
            return httpx.Response(200, json={"license": "MIT"})
        return httpx.Response(404)

    client = client_for(handler, failure_budget=3)
    for index in range(5):
        client.npm(f"pkg{index}", "1.0.0")

    # Without the reset, the two failures after the 404 would reach the
    # budget and the final lookup would never be attempted.
    assert client.npm("pkg-final", "1.0.0") == {"license": "MIT"}


@pytest.mark.parametrize(
    "declared",
    [
        "RegistrationsBaseUrl",
        "RegistrationsBaseUrl/3.6.0",
        ["RegistrationsBaseUrl/3.6.0", "RegistrationsBaseUrl"],
        ["RegistrationsBaseUrl/3.4.0"],
    ],
)
def test_nuget_registration_is_found_whatever_shape_the_type_takes(declared):
    """The service index versions `@type` and sometimes lists it. Exact
    equality against the bare name made every .NET lookup return nothing."""

    def handler(request):
        url = str(request.url)
        if url.endswith("index.json"):
            return httpx.Response(
                200,
                json={
                    "resources": [
                        {"@type": "SearchQueryService", "@id": "https://s/"},
                        {"@type": declared, "@id": "https://reg/"},
                    ]
                },
            )
        if url.startswith("https://reg/"):
            return httpx.Response(200, json={"catalogEntry": "https://cat/1"})
        return httpx.Response(200, json={"licenseExpression": "MIT"})

    assert client_for(handler).nuget("Newtonsoft.Json", "13.0.1") == {"license": "MIT"}


def test_an_index_without_a_registration_resource_returns_nothing():
    def handler(request):
        return httpx.Response(200, json={"resources": [{"@type": "Other", "@id": "x"}]})

    assert client_for(handler).nuget("Some.Package", "1.0.0") == {}
