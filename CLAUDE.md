# CLAUDE.md

See `AGENTS.md` for the canonical repo instructions.

- Python `3.11+`
- Use `uv sync`, `uv run python -m unittest discover -s tests -p 'test_*.py' -v`, `uv run dotenvdrift examples/broken-repo`, and `uv build`
- Keep detection generic and deterministic
- Do not add AWS / GCP / Azure / crypto-specific logic, auto-fix behavior, or config files
- Never print env values, only names and locations
