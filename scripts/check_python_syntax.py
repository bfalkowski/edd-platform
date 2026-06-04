from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_ROOTS = [
    ROOT / "apps" / "api" / "edd_platform_api",
    ROOT / "apps" / "api" / "tests",
    ROOT / "packages" / "domain" / "edd_domain",
    ROOT / "packages" / "langfuse-adapter" / "edd_langfuse_adapter",
    ROOT / "packages" / "langfuse-adapter" / "tests",
    ROOT / "packages" / "runner" / "edd_runner",
    ROOT / "scripts",
]


def main() -> None:
    checked = 0
    for root in CHECK_ROOTS:
        for path in sorted(root.rglob("*.py")):
            ast.parse(path.read_text(), filename=str(path))
            checked += 1
    print(f"Python syntax check passed for {checked} files.")


if __name__ == "__main__":
    main()
