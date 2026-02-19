[![Python Release](https://github.com/StartupOS/verinfast/actions/workflows/release.yml/badge.svg?event=release)](https://github.com/StartupOS/verinfast/actions/workflows/release.yml)
[![codecov](https://codecov.io/gh/StartupOS/verinfast/graph/badge.svg?token=IECR8RD60P)](https://codecov.io/gh/StartupOS/verinfast)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)
# VerinFast™

Scan your codebase to reveal language breakdown, dependencies, OWASP vulnerabilities, cloud costs, and exactly what AI is adding to your application.

## Installation

### pip

```sh
pip install verinfast
```

### pipx

```sh
pipx install verinfast
```

### Poetry

```sh
poetry add verinfast
```

### Docker

```sh
docker build -t verinfast .
docker run --rm -v $(pwd):/usr/src/app verinfast
```

## Requirements

- Python 3.9+ (test with `python3 --version`)
- SSH access to code repositories (test with `git status`)
- Command line tool access to cloud hosting providers (AWS CLI, Azure CLI, or gcloud)
- Your dependency management tools (e.g. `npm`, `yarn`, `maven`, `pip`, `poetry`)
- Outbound internet access (for posting results and fetching dependency metadata)

## Usage

```sh
# Run in a directory with a config.yaml file
verinfast

# Point to a specific config file
verinfast --config=/path/to/config.yaml

# Set a custom output directory
verinfast --output=/path/to/output

# Check the installed version
verinfast --version
```

## Config Options

If you want to check the output for yourself you can set `should_upload: false`, and use the flag `--output=/path/to/dir`. This will give you the chance to inspect what we collect before uploading. For large repositories, it is a lot of information, but we never upload your code or any credentials, just the summary data we collect.

## Troubleshooting

### Python
- Run `python3 -m pip install --upgrade pip setuptools wheel`

### git
- Run `which git`, `git --version`
- Run `ssh -vT git@github.com` to test access to GitHub

### AWS
- Run `which aws`, `aws --version`

### Azure
- Run `az login`, `az --version`
- Run `az account subscription list` to check subscription Id

### GCP
- Run `which gcloud`, `gcloud --version`

### Semgrep
- Run `which semgrep`, `semgrep --version`

Copyright ©2023-2026 Startos Inc.
