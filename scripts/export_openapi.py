from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from edd_platform_api.main import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI contract.")
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "openapi.json"),
        help="Output path for the generated OpenAPI JSON.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
