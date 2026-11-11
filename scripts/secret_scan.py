"""Small high-confidence secret scanner for tracked repository content."""

from __future__ import annotations

import re
import subprocess
import tempfile
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
    ("anthropic_token", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    # A Solana CLI keypair file (``id.json``) is a JSON array of 64 byte values.
    # Base58-encoded secret keys are not matched because they are
    # indistinguishable from 88-character transaction signatures.
    (
        "solana_keypair_json",
        re.compile(r"\[\s*(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*){63}(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*\]"),
    ),
    (
        "api_key_query_uuid",
        re.compile(
            r"(?i)[?&]api[-_]?key=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
        ),
    ),
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
        except UnicodeDecodeError:
            continue
        findings.extend((path, finding) for finding in scan_text(text))
    return findings


def scan_artifacts(root: Path) -> list[tuple[Path, SecretFinding]]:
    """Scan ignored release artifacts and logs without exposing their contents."""

    return scan_files(artifact_files(root))


@lru_cache(maxsize=4)
def _scan_git_history_cached(
    root_text: str, refs: bytes
) -> tuple[tuple[Path, SecretFinding], ...]:
    """Scan reachable git blobs while returning only safe object/path metadata."""

    root = Path(root_text)

    objects = subprocess.run(
        ["git", "-C", str(root), "rev-list", "--objects", "--all"],
        check=True,
        capture_output=True,
    )
    object_paths: list[tuple[str, str]] = []
    for raw_line in objects.stdout.splitlines():
        object_id, separator, raw_path = raw_line.partition(b" ")
        if separator and len(object_id) == 40 and raw_path:
            object_paths.append((object_id.decode("ascii"), raw_path.decode("utf-8", "replace")))
    if not object_paths:
        return ()
    by_id = dict(object_paths)
    findings: list[tuple[Path, SecretFinding]] = []
    with tempfile.TemporaryFile() as requests:
        requests.write(("\n".join(by_id) + "\n").encode("ascii"))
        requests.seek(0)
        with subprocess.Popen(
            ["git", "-C", str(root), "cat-file", "--batch"],
            stdin=requests,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as process:
            assert process.stdout is not None
            for expected_id in by_id:
                header = process.stdout.readline().split()
                if len(header) != 3 or header[0].decode("ascii") != expected_id:
                    raise RuntimeError("incomplete Git history scan")
                size = int(header[2])
                content = process.stdout.read(size)
                if len(content) != size or process.stdout.read(1) != b"\n":
                    raise RuntimeError("truncated Git history object")
                if header[1] == b"blob":
                    safe_path = root / "git-history" / expected_id[:12] / by_id[expected_id]
                    findings.extend(
                        (safe_path, finding)
                        for finding in scan_text(content.decode("utf-8", "ignore"))
                    )
            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, process.args)
    return tuple(findings)


def scan_git_history(root: Path) -> list[tuple[Path, SecretFinding]]:
    """Scan reachable git blobs while returning only safe object/path metadata."""

    resolved = root.resolve()
    refs = subprocess.run(
        ["git", "-C", str(resolved), "for-each-ref", "--format=%(refname) %(objectname)"],
        check=True,
        capture_output=True,
    ).stdout
    return list(_scan_git_history_cached(str(resolved), refs))


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
