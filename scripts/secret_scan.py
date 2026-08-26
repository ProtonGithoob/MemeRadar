"""Small high-confidence secret scanner for tracked repository content."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
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


def scan_files(paths: Iterable[Path]) -> list[tuple[Path, SecretFinding]]:
    findings: list[tuple[Path, SecretFinding]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend((path, finding) for finding in scan_text(text))
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_files(tracked_files(root))
    for path, finding in findings:
        print(f"{finding.rule}: {path.relative_to(root)}:{finding.line}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
