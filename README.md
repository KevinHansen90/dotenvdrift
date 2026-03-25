<p align="center">
  <img src="https://raw.githubusercontent.com/KevinHansen90/dotenvdrift/main/docs/assets/dotenvdrift-logo.png" alt="dotenvdrift logo" width="720">
</p>

<h1 align="center">dotenvdrift</h1>

<p align="center">
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-2ea44f" alt="MIT License">
  </a>
</p>

Small repo-local CLI that catches env drift between code, `.env.example`, Docker / docker-compose, and GitHub Actions.

## Why

I built this after repeatedly hitting env drift while moving quickly, including with coding agents: the code was done, but `.env.example`, Docker, docker-compose, and GitHub Actions had drifted apart.

That failure mode is not specific to AI-assisted repos. It breaks onboarding, local runs, and CI in any repo. This tool is just especially handy in fast-moving codebases where config drift shows up early.

## What It Checks

- `missing`: used in code but absent from `.env.example`
- `undocumented`: referenced in Docker or GitHub Actions but not documented locally
- `unused`: still listed in `.env.example` but no longer referenced

It scans Python and JS/TS code, `.env.example`, Docker / docker-compose files, and GitHub Actions workflows with simple deterministic patterns.

## Install

Requires Python 3.11+.

```bash
uv sync
```

Fallback:

```bash
python -m pip install .
```

## Usage

```bash
uv run dotenvdrift .
uv run dotenvdrift examples/broken-repo
uv run dotenvdrift . --json
uv run dotenvdrift . --strict
uv run dotenvdrift . --only missing
```

Sample output:

```text
missing
  NODE_ENV             web/client.ts:2
  OPENAI_API_KEY       app/settings.py:4
  VITE_API_BASE_URL    web/client.ts:1

undocumented
  DATABASE_URL         docker-compose.yml:5
  PYPI_TOKEN           .github/workflows/release.yml:11
  RELEASE_REGION       .github/workflows/release.yml:7

unused
  DEBUG_SQL            .env.example:2

✗ 7 drift issues
```

## Limits

- It never loads or prints env values, only names and locations.
- It uses line-based regex scans, not ASTs or YAML parsers.
- It stays generic. AWS, GCP, Azure, and crypto repos work when they use env vars, but there is no provider-specific logic.
- It does not sync secrets, manage vaults, validate schemas, or auto-fix anything.

## Development

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
uv build
```

## Exit Codes

- `0`: no issues, or issues found without `--strict`
- `1`: issues found with `--strict`
- `2`: invalid repository path

## License

MIT
