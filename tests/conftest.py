"""
conftest.py — shared fixtures and helpers for the DQ test suite.

Import from any test module:
    from conftest import assert_pass, assert_fail, assert_in_details, SAMPLE_DATA, ...
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def assert_pass(result, msg: str = "") -> None:
    assert result.passed, f"Expected PASS but got FAIL: {result.message}  {msg}"


def assert_fail(result, msg: str = "") -> None:
    assert not result.passed, f"Expected FAIL but got PASS: {result.message}  {msg}"


def assert_in_details(result, key: str) -> None:
    assert key in result.details, f"Expected '{key}' in details, got: {result.details}"


# ---------------------------------------------------------------------------
# Shared sample datasets
# ---------------------------------------------------------------------------

CLEAN_ROW = {"id": 1, "name": "Alice", "age": 30, "salary": 50000,
             "email": "alice@example.com", "status": "active", "dept": "Eng"}

SAMPLE_DATA = [
    {"id": 1, "name": "Alice", "age": 30, "salary": 50000,
     "email": "alice@example.com", "status": "active", "dept": "Eng"},
    {"id": 2, "name": "Bob",   "age": 25, "salary": 60000,
     "email": "bob@example.com",   "status": "inactive", "dept": "HR"},
    {"id": 3, "name": "Carol", "age": 35, "salary": 55000,
     "email": "carol@example.com", "status": "active",   "dept": "Fin"},
]

SINGLE_ROW = [CLEAN_ROW.copy()]

EMPTY_DATA: list[dict] = []

# Paths used by CLI and facade tests
BASE_DIR = Path(__file__).parent.parent
CLI_ENTRY = BASE_DIR / "cli.py"
# Auto-create dq_cli.py if missing (works with `pip install -e .`)
if not CLI_ENTRY.exists():
    CLI_ENTRY.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent / 'src'))\n"
        "from Iki_DQ_Check.app import main\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
FACADE_PATH = BASE_DIR / "data_quality" / "facade.py"
DATA_JSON = BASE_DIR / "sample_data.json"
DATA_CSV = BASE_DIR / "sample_data.csv"
CONFIG = BASE_DIR / "config.yaml"

# Dataset with intentional issues — used by facade tests to verify failures
DIRTY_DATA = [
    {"id": 1, "name": "Alice", "age": 30,   "salary": 50000,
        "email": "alice@example.com", "status": "active"},
    {"id": 2, "name": "Bob",   "age": None, "salary": -9999,
        "email": "not-an-email",       "status": "deleted"},
    {"id": 2, "name": "Carol", "age": 35,   "salary": 55000,
        "email": "carol@example.com",  "status": "active"},
]
