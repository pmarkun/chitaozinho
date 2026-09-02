#!/usr/bin/env python3
"""Reject generated files in Git and broken local Markdown links."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIRECTORIES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "target",
    "test-results",
}
GENERATED_NAMES = {".DS_Store"}
GENERATED_SUFFIXES = {".bak", ".log", ".orig", ".tmp", ".tsbuildinfo"}
LINK = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "app:", "data:")


def git_paths(*arguments: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [Path(value.decode()) for value in result.stdout.split(b"\0") if value]


def generated_files() -> list[Path]:
    offenders = []
    for path in git_paths("--cached"):
        if (
            GENERATED_DIRECTORIES.intersection(path.parts)
            or path.name in GENERATED_NAMES
            or path.suffix in GENERATED_SUFFIXES
        ):
            offenders.append(path)
    return offenders


def markdown_files() -> list[Path]:
    return [
        path
        for path in git_paths("--cached", "--others", "--exclude-standard")
        if path.suffix.lower() == ".md" and (ROOT / path).is_file()
    ]


def broken_links() -> list[str]:
    offenders = []
    for relative_path in markdown_files():
        source = ROOT / relative_path
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            for match in LINK.finditer(line):
                target = match.group("target").strip("<>")
                if target.startswith(("#", "/", *EXTERNAL_SCHEMES)):
                    continue
                local_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if local_path and not (source.parent / local_path).exists():
                    offenders.append(f"{relative_path}:{line_number}: {target}")
    return offenders


def main() -> None:
    errors = []
    generated = generated_files()
    if generated:
        errors.append("generated files are tracked:\n" + "\n".join(map(str, generated)))
    links = broken_links()
    if links:
        errors.append("local Markdown links are broken:\n" + "\n".join(links))
    if errors:
        raise SystemExit("\n\n".join(errors))
    print("Repository hygiene valid: no generated files or broken local Markdown links")


if __name__ == "__main__":
    main()
