from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .__init__ import __version__
from .core import AuditResult, audit, select_issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dotenvdrift",
        description="Catch env var drift between code, .env.example, Docker, and GitHub Actions.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository path")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any issue is found")
    parser.add_argument(
        "--only",
        choices=("missing", "undocumented", "unused"),
        help="Show a single issue group",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit(args.path)
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(render_json(result, args.only))
    else:
        print(render_text(result, args.only))
    total = sum(len(items) for _, items in select_issues(result, args.only))
    return 1 if args.strict and total else 0


def render_json(result: AuditResult, only: str | None) -> str:
    payload = {
        "root": result.root,
        "documented_files": result.documented_files,
        "counts": result.counts(only),
        "issues": {
            name: [asdict(issue) for issue in issues]
            for name, issues in select_issues(result, only)
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_text(result: AuditResult, only: str | None) -> str:
    groups = select_issues(result, only)
    total = sum(len(items) for _, items in groups)
    if total == 0:
        return "✓ no env drift found"

    lines: list[str] = []
    for name, issues in groups:
        if not issues:
            continue
        lines.append(name)
        for issue in issues:
            label = issue.name.ljust(20)
            if issue.first_seen:
                lines.append(f"  {label} {issue.first_seen}")
            else:
                lines.append(f"  {label}")
        lines.append("")
    lines.append(f"✗ {total} drift issue{'s' if total != 1 else ''}")
    return "\n".join(lines).rstrip()
