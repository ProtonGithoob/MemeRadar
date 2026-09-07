"""Small high-confidence secret scanner for tracked repository content."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SecretFinding:
    rule: str
    line: int


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_token", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("telegram_bot_token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)


def scan_text(text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for rule, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append(SecretFinding(rule=rule, line=text.count("\n", 0, match.start()) + 1))
    return sorted(findings, key=lambda finding: (finding.line, finding.rule))


def tracked_files(root: Path) -> Iterable[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    for raw_path in result.stdout.split(b"\0"):
        if raw_path:
            yield root / raw_path.decode("utf-8")


def artifact_files(root: Path) -> Iterable[Path]:
    """Yield bounded generated/release locations without traversing dependencies."""

    roots = (
        "artifacts",
        "dist",
        "build",
        "out",
        "logs",
        "apps/web/.next/static",
        "apps/web/.next/server",
        "apps/web/.next/dev/logs",
        "apps/web/.next/standalone/.next/static",
    )
    seen: set[Path] = set()
    for relative in roots:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path
    for path in root.glob("*.log"):
        if path.is_file() and path not in seen:
            yield path


def scan_files(paths: Iterable[Path]) -> list[tuple[Path, SecretFinding]]:
    findings: list[tuple[Path, SecretFinding]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend((path, finding) for finding in scan_text(text))
    return findings


def scan_artifacts(root: Path) -> list[tuple[Path, SecretFinding]]:
    """Scan ignored release artifacts and logs without exposing their contents."""

    return scan_files(artifact_files(root))


@lru_cache(maxsize=4)
def _scan_git_history_cached(root_text: str) -> tuple[tuple[Path, SecretFinding], ...]:
    """Scan reachable git blobs while returning only safe object/path metadata."""

    root = Path(root_text)

    try:
        objects = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--objects", "--all"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ()
    object_paths: list[tuple[str, str]] = []
    for raw_line in objects.stdout.splitlines():
        object_id, separator, raw_path = raw_line.partition(b" ")
        if separator and len(object_id) == 40 and raw_path:
            object_paths.append((object_id.decode("ascii"), raw_path.decode("utf-8", "replace")))
    if not object_paths:
        return ()
    try:
        blobs = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            input=("\n".join(object_id for object_id, _ in object_paths) + "\n").encode("ascii"),
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ()
    by_id = dict(object_paths)
    findings: list[tuple[Path, SecretFinding]] = []
    payload = blobs.stdout
    offset = 0
    while offset < len(payload):
        header_end = payload.find(b"\n", offset)
        if header_end < 0:
            break
        header = payload[offset:header_end].split()
        if len(header) != 3:
            break
        object_id, object_type, raw_size = header
        try:
            size = int(raw_size)
        except ValueError:
            break
        content_start = header_end + 1
        content_end = content_start + size
        content = payload[content_start:content_end]
        offset = content_end + 1
        if object_type != b"blob" or object_id.decode("ascii", "ignore") not in by_id:
            continue
        text = content.decode("utf-8", "ignore")
        safe_path = root / "git-history" / object_id[:12].decode("ascii") / by_id[
            object_id.decode("ascii")
        ]
        findings.extend((safe_path, finding) for finding in scan_text(text))
    return tuple(findings)


def scan_git_history(root: Path) -> list[tuple[Path, SecretFinding]]:
    """Scan reachable git blobs while returning only safe object/path metadata."""

    return list(_scan_git_history_cached(str(root.resolve())))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = [
        *scan_files(tracked_files(root)),
        *scan_artifacts(root),
        *scan_git_history(root),
    ]
    for path, finding in findings:
        print(f"{finding.rule}: {path.relative_to(root)}:{finding.line}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
