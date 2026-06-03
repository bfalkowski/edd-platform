from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TRACKED_ENV_FILES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".envrc",
}

SECRET_PATTERNS = [
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-api03-[A-Za-z0-9_-]{24,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{24,}\b")),
    ("LangSmith API key", re.compile(r"\blsv2_[A-Za-z0-9_=-]{24,}\b")),
]

ASSIGNMENT_PATTERNS = [
    (
        "OPENAI_API_KEY assignment",
        re.compile(r"\bOPENAI_API_KEY\s*=\s*['\"]?(?!sk-\.\.\.|\.{3}|<|your_|REDACTED\b)([^'\"\s#]+)"),
    ),
    (
        "ANTHROPIC_API_KEY assignment",
        re.compile(r"\bANTHROPIC_API_KEY\s*=\s*['\"]?(?!\.{3}|<|your_|REDACTED\b)([^'\"\s#]+)"),
    ),
]


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:1024]
    except OSError:
        return True
    return b"\0" in chunk


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_file(path: Path) -> list[str]:
    relative = path.relative_to(ROOT)
    issues: list[str] = []
    if relative.name in TRACKED_ENV_FILES:
        issues.append(f"{relative}: tracked environment file")
        return issues
    if is_binary(path):
        return issues

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return issues

    for label, pattern in SECRET_PATTERNS + ASSIGNMENT_PATTERNS:
        for match in pattern.finditer(text):
            issues.append(f"{relative}:{line_number(text, match.start())}: {label}")
    return issues


def main() -> int:
    issues: list[str] = []
    for path in tracked_files():
        issues.extend(scan_file(path))

    if issues:
        print("Secret scan failed. Remove secrets from tracked files:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
