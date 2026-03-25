# AGENTS.md

Canonical repo instructions for coding agents.

## Setup commands

- Python: `3.11+`
- Sync the repo env: `uv sync`
- Run tests: `uv run python -m unittest discover -s tests -p 'test_*.py' -v`
- Run the example: `uv run dotenvdrift examples/broken-repo`
- Build packages: `uv build`

## Project shape

- Keep runtime code in `src/dotenvdrift/`
- Keep core logic in `core.py`
- Keep CLI glue in `cli.py`
- Keep the package stdlib-only unless a dependency removes a lot of code

## Guardrails

- Never print env values, only names and locations
- Keep detection generic and deterministic
- Do not add AWS / GCP / Azure / crypto-specific logic in v1
- Prefer simple regex and line-based scanning over AST or YAML parsers
- Do not add auto-fix behavior in this repo
- Do not add a config file unless there is a concrete user need
- Keep output short enough to read in one terminal screen

## Style

- Small functions
- Direct names
- Minimal comments
- No framework layers
- No speculative abstractions
