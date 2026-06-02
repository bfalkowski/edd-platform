import sys
from pathlib import Path

from edd_platform_api.main import app

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.lint_openapi import REQUIRED_PATHS, lint_openapi


def test_openapi_contract_lints() -> None:
    assert lint_openapi(app.openapi()) == []


def test_openapi_contract_contains_required_paths() -> None:
    paths = set(app.openapi()["paths"])

    assert REQUIRED_PATHS <= paths
