"""Payload fixtures copied from ATD v3's own agent-contract test.

The mirror image of what ATD did to us: its
``services/atd/api/tests/e2e/upload_paths.py`` is a literal port of our
:mod:`verinfast2.transport.paths`, so that its contract test builds request
paths the way the real agent does. This file is the same trade in the other
direction — the payload shapes ATD asserts against, vendored here so our
contract test proves we send what it expects without needing a Postgres, a
running ATD, or a network.

Source: ``VerinFast/good-place@74e41ff``,
``services/atd/api/tests/e2e/test_agent_contract.py``. Copied verbatim, with
the comments that explain *why* each odd value is in there — they are the
actual specification:

- git numstat values stay **strings**, including ``"-"`` for binary files;
- an author may arrive with no ``<email>`` part;
- sizes carries a ``"."`` root entry, which ATD lifts onto the repository row;
- modernmetric paths may contain ``temp_repo/``, which ATD rewrites to ``./``
  (v2 should stop producing those, and the fixture stays to prove the
  rewrite still works for agents in the field);
- ``metadata.cwe`` may be a bare string rather than a list.

Keep in sync by hand. :mod:`test_atd_contract` fails loudly if the
shapes stop matching what we send.
"""

from __future__ import annotations

from typing import Any

GIT_PAYLOAD: list[dict[str, Any]] = [
    {
        "commit": "abc123def456",
        "author": "Ada Lovelace <ada@example.com>",
        "date": "Wed, 21 Feb 2024 10:00:00 +0000",
        "message": "Add analytical engine bindings",
        "signed": True,
        "merge": False,
        "paths": [
            {"insertions": "12", "deletions": "3", "path": "src/engine.py"},
            # numstat emits "-" for binary files -- must coerce to 0, not crash.
            {"insertions": "-", "deletions": "-", "path": "assets/logo.png"},
        ],
    },
    {
        "commit": "deadbeef0001",
        "author": "Grace Hopper",  # no "<email>" -- must tolerate missing email
        "date": "Thu, 22 Feb 2024 11:30:00 +0000",
        "message": "Merge branch 'feature/compiler'",
        "signed": False,
        "merge": True,
        "paths": [{"insertions": "5", "deletions": "2", "path": "src/compiler.py"}],
    },
]

SIZES_PAYLOAD: dict[str, Any] = {
    "metadata": {
        "env": "x86_64",
        "real_size": 4096,
        "uname": "Linux",
        "branch": "main",
    },
    "files": {
        ".": {"size": 4096, "loc": 0, "ext": None, "directory": True},
        "src/engine.py": {"size": 512, "loc": 40, "ext": "py", "directory": False},
        "src/compiler.py": {"size": 256, "loc": 20, "ext": "py", "directory": False},
    },
}

STATS_PAYLOAD: dict[str, Any] = {
    "files": {
        "src/engine.py": {
            "code_loc": 32,
            "comment_ratio": 0.2,
            "cyclomatic_complexity": 4.0,
            "lang": ["Python"],
        },
        # modernmetric reports paths rooted in the agent's clone dir --
        # temp_repo/... must be rewritten to ./....
        "/home/agent/.verinfast/temp_repo/src/compiler.py": {
            "code_loc": 18,
            "comment_ratio": 0.1,
            "cyclomatic_complexity": 2.0,
            "lang": "Python",
        },
    },
    "overall": {
        "comment_ratio": 0.15,
        "cyclomatic_complexity": 3.0,
        "maintainability_index": 71.5,
    },
    "stats": {
        "mean": {"cyclomatic_complexity": 3.0, "loc": 26},
        "median": {"cyclomatic_complexity": 3.0, "loc": 26},
        "min": {"cyclomatic_complexity": 2.0, "loc": 18},
        "max": {"cyclomatic_complexity": 4.0, "loc": 32},
        "sd": {"cyclomatic_complexity": 1.0, "loc": 7.0},
    },
}

FINDINGS_PAYLOAD: dict[str, Any] = {
    "version": "1.152.0",
    "errors": [],
    "results": [
        {
            "check_id": "python.lang.security.audit.eval-detected",
            "path": "src/engine.py",
            "start": {"line": 10, "col": 1, "offset": 100},
            "end": {"line": 10, "col": 20, "offset": 119},
            "extra": {
                "fingerprint": "abc123",
                "lines": "eval(user_input)",
                "message": "Detected use of eval().",
                "severity": "ERROR",
                "metadata": {
                    "category": "security",
                    # semgrep sometimes emits a bare string, not an array --
                    # ingest must normalize either shape.
                    "cwe": "CWE-95: Eval Injection",
                    "owasp": ["A03:2021"],
                    "shortlink": "https://sg.run/abc",
                    "technology": ["python"],
                },
            },
        }
    ],
}

DEPENDENCIES_PAYLOAD: list[dict[str, Any]] = [
    {
        "name": "requests",
        "source": "pypi",
        "specifier": "==2.31.0",
        "license": "Apache-2.0",
        "summary": "Python HTTP for Humans.",
        "required_by": "sample-app",
    },
    {
        "name": "flask",
        "source": "pypi",
        "specifier": ">=3.0",
        "required_by": ["sample-app"],
    },
]


def cloud_envelope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"metadata": {"provider": "aws", "account": "123456789012"}, "data": rows}


COSTS_PAYLOAD = cloud_envelope(
    [{"Date": "2024-02-01", "Group": "EC2", "Cost": "12.34", "Currency": "USD"}]
)

INSTANCES_PAYLOAD = cloud_envelope(
    [
        {
            "id": "i-0abc123",
            "name": "web-1",
            "type": "t3.micro",
            "state": "running",
            "zone": "us-east-1a",
            "region": "us-east-1",
            "subnet": "subnet-1",
            "architecture": "x86_64",
            "publicIp": "n/a",
            "vpc": "vpc-1",
        }
    ]
)

UTILIZATION_PAYLOAD = cloud_envelope(
    [
        {
            "id": "i-0abc123",
            "metrics": [
                {
                    "timestamp": 1700000000,
                    "cpu": {"minimum": 1.0, "average": 5.0, "maximum": 20.0},
                    "mem": None,
                    "hdd": None,
                }
            ],
        }
    ]
)

STORAGE_PAYLOAD = cloud_envelope(
    [
        {
            "name": "sample-app-artifacts",
            "size": 1024,
            "retention": "30d",
            "public": False,
            "permissions": ["owner:rw", "public:none"],
        }
    ]
)

#: The document ATD's ``build_agent_config`` renders, with its exact keys.
#: Source: ``services/atd/api/atd_api/services/code_scan.py``.
SERVED_CONFIG_YAML = """\
baseurl: https://atd.example/api
should_upload: true
dry: false
truncate_findings: true
truncate_findings_length: 30
report:
  uuid: 9a6e8696-f93a-4402-a64e-342ccb37592b
server:
  code_separator: /CodeScan
modules:
  code:
    git:
      start: '2025-03-01'
    dependencies: true
  cloud:
  - provider: aws
    account: '123456789012'
    start: '2025-03-01'
    end: '2025-09-23'
repos:
- https://github.com/example/sample-app.git
local_repos:
- /srv/checkouts/my-local-checkout
"""
