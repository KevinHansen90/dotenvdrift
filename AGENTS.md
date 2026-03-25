# AGENTS.md

## Purpose

Detect env var drift across code, `.env.example`, Docker / docker-compose, and GitHub Actions.

## Run

`uv run dotenvdrift .`

## Test

`uv run python -m unittest discover -s tests -p 'test_*.py' -v`

## Principles

- keep code small and deterministic
- keep detection generic
- no dependencies unless necessary
- prefer deletion over addition
- never print env values, only names and locations
