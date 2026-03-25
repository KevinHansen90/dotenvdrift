# Copilot Instructions

- Python `3.11+`
- Use `uv sync`
- Test with `uv run python -m unittest discover -s tests -p 'test_*.py' -v`
- Run the example with `uv run dotenvdrift examples/broken-repo`
- Build with `uv build`
- Keep runtime code in `src/dotenvdrift/`
- Keep core logic in `core.py` and CLI glue in `cli.py`
- Keep the package stdlib-only unless a dependency removes substantial code
- Keep detection generic and deterministic across code, `.env.example`, Docker, and GitHub Actions
- Do not add AWS / GCP / Azure / crypto-specific logic, auto-fix behavior, or config files
- Never print env values, only names and locations
