from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import re

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
YAML_EXTENSIONS = {".yml", ".yaml"}
MAX_FILE_BYTES = 1_000_000
VAR_RE = r"[A-Z][A-Z0-9_]*"

PYTHON_PATTERNS = (
    re.compile(rf"os\.getenv\(\s*[\"']({VAR_RE})[\"']"),
    re.compile(rf"os\.environ\.get\(\s*[\"']({VAR_RE})[\"']"),
    re.compile(rf"os\.environ\[\s*[\"']({VAR_RE})[\"']\s*\]"),
)
JS_PATTERNS = (
    re.compile(rf"process\.env\.({VAR_RE})\b"),
    re.compile(rf"process\.env\[\s*[\"']({VAR_RE})[\"']\s*\]"),
    re.compile(rf"import\.meta\.env\.({VAR_RE})\b"),
)
ACTIONS_INLINE_PATTERNS = (
    re.compile(rf"\$\{{\{{\s*secrets\.({VAR_RE})\s*\}}\}}"),
    re.compile(rf"\$\{{\{{\s*vars\.({VAR_RE})\s*\}}\}}"),
)
DOCKER_SUBSTITUTION = re.compile(rf"\$\{{({VAR_RE})(?::-[^}}]*)?\}}")
ENV_KEY_LINE = re.compile(rf"^({VAR_RE})\s*:")
ENV_FILE_KEY = re.compile(rf"^(?:export\s+)?({VAR_RE})\s*=")


@dataclass(frozen=True, slots=True)
class Hit:
    source: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class Issue:
    kind: str
    name: str
    first_seen: str | None


@dataclass(slots=True)
class AuditResult:
    root: str
    documented_files: list[str]
    missing: list[Issue]
    undocumented: list[Issue]
    unused: list[Issue]

    def counts(self, only: str | None = None) -> dict[str, int]:
        counts = {"missing": 0, "undocumented": 0, "unused": 0}
        for name, issues in select_issues(self, only):
            counts[name] = len(issues)
        counts["total"] = counts["missing"] + counts["undocumented"] + counts["unused"]
        return counts


class ReferenceIndex:
    def __init__(self) -> None:
        self._hits: dict[str, list[Hit]] = defaultdict(list)

    def add(self, name: str, source: str, path: Path, line: int) -> None:
        hit = Hit(source=source, path=path.as_posix(), line=line)
        if hit not in self._hits[name]:
            self._hits[name].append(hit)

    def names(self) -> set[str]:
        return set(self._hits)

    def hits_for(self, name: str) -> list[Hit]:
        return self._hits.get(name, [])

    def first_seen(self, name: str) -> str | None:
        hits = self.hits_for(name)
        if not hits:
            return None
        first = sorted(hits, key=lambda item: (item.path, item.line))[0]
        return f"{first.path}:{first.line}"

    def has_source(self, name: str, source: str) -> bool:
        return any(hit.source == source for hit in self.hits_for(name))


def audit(root: str | Path) -> AuditResult:
    base = resolve_root(root)
    documented, documented_files, documented_locations = read_documented_keys(base)
    refs = collect_references(base)

    missing_names = sorted(
        name for name in refs.names() if name not in documented and refs.has_source(name, "code")
    )
    undocumented_names = sorted(
        name
        for name in refs.names()
        if name not in documented
        and not refs.has_source(name, "code")
        and (refs.has_source(name, "actions") or refs.has_source(name, "docker"))
    )
    unused_names = sorted(name for name in documented if name not in refs.names())

    return AuditResult(
        root=base.as_posix(),
        documented_files=documented_files,
        missing=[Issue("missing", name, refs.first_seen(name)) for name in missing_names],
        undocumented=[Issue("undocumented", name, refs.first_seen(name)) for name in undocumented_names],
        unused=[Issue("unused", name, documented_locations.get(name)) for name in unused_names],
    )


def resolve_root(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"repository path not found: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"repository path is not a directory: {base}")
    return base


def read_documented_keys(root: Path) -> tuple[set[str], list[str], dict[str, str]]:
    files: list[str] = []
    keys: set[str] = set()
    locations: dict[str, str] = {}
    for path in walk_files(root):
        if path.name != ".env.example":
            continue
        relative = path.relative_to(root).as_posix()
        files.append(relative)
        for line_number, raw_line in enumerate(read_text(path).splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = ENV_FILE_KEY.match(line)
            if match:
                name = match.group(1)
                keys.add(name)
                locations.setdefault(name, f"{relative}:{line_number}")
    return keys, sorted(files), locations


def collect_references(root: Path) -> ReferenceIndex:
    refs = ReferenceIndex()
    for path in walk_files(root):
        if is_oversized(path):
            continue
        suffix = path.suffix.lower()
        text = read_text(path)
        rel_path = path.relative_to(root)
        if suffix in CODE_EXTENSIONS:
            if suffix == ".py":
                scan_patterns(text, rel_path, PYTHON_PATTERNS, refs, "code")
            else:
                scan_patterns(text, rel_path, JS_PATTERNS, refs, "code")
            continue
        if suffix in YAML_EXTENSIONS:
            if is_actions_file(rel_path):
                scan_actions(text, rel_path, refs)
            elif is_compose_file(rel_path):
                scan_compose(text, rel_path, refs)
    return refs


def scan_patterns(text: str, path: Path, patterns: tuple[re.Pattern[str], ...], refs: ReferenceIndex, source: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            for match in pattern.finditer(line):
                refs.add(match.group(1), source, path, line_number)


def scan_actions(text: str, path: Path, refs: ReferenceIndex) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in ACTIONS_INLINE_PATTERNS:
            for match in pattern.finditer(line):
                refs.add(match.group(1), "actions", path, line_number)
    scan_yaml_block_keys(text, path, refs, block_name="env", source="actions")


def scan_compose(text: str, path: Path, refs: ReferenceIndex) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in DOCKER_SUBSTITUTION.finditer(line):
            refs.add(match.group(1), "docker", path, line_number)
    scan_yaml_block_keys(text, path, refs, block_name="environment", source="docker")


def scan_yaml_block_keys(text: str, path: Path, refs: ReferenceIndex, *, block_name: str, source: str) -> None:
    active_indent: int | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if active_indent is not None and indent <= active_indent:
            active_indent = None
        if stripped == f"{block_name}:" or stripped.startswith(f"{block_name}: #"):
            active_indent = indent
            continue
        if active_indent is None:
            continue
        match = ENV_KEY_LINE.match(stripped)
        if match:
            refs.add(match.group(1), source, path, line_number)
            continue
        if stripped.startswith("- "):
            list_match = re.match(rf"-\s*({VAR_RE})=", stripped)
            if list_match:
                refs.add(list_match.group(1), source, path, line_number)


def walk_files(root: Path) -> Iterator[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORE_DIRS)
        for filename in sorted(filenames):
            yield Path(current_root, filename)


def is_oversized(path: Path) -> bool:
    try:
        return path.stat().st_size > MAX_FILE_BYTES
    except OSError:
        return True


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    except OSError:
        return ""


def is_actions_file(path: Path) -> bool:
    parts = path.parts
    return len(parts) >= 3 and parts[0] == ".github" and parts[1] == "workflows"


def is_compose_file(path: Path) -> bool:
    name = path.name.lower()
    return name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}


def select_issues(result: AuditResult, only: str | None = None) -> list[tuple[str, list[Issue]]]:
    groups = [
        ("missing", result.missing),
        ("undocumented", result.undocumented),
        ("unused", result.unused),
    ]
    if only is None:
        return groups
    return [group for group in groups if group[0] == only]
