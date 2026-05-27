"""
test_loaders.py — Unit tests for CLI data and config loaders.

Covers: load_data (JSON, CSV), coerce, load_config, resolve_config,
        safe_eval_rule, and error paths.
"""

from __future__ import annotations
from Iki_DQ_Check import load_data, load_config, coerce, resolve_config, safe_eval_rule

import json
from datetime import datetime
from pathlib import Path

import pytest

# Import loader functions from the CLI module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# ===========================================================================
# load_data — JSON
# ===========================================================================

class TestLoadDataJson:

    def _write(self, tmp, content: str, name="data.json") -> str:
        p = Path(tmp) / name
        p.write_text(content)
        return str(p)

    def test_loads_top_level_list(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps([{"id": 1}, {"id": 2}]))
        rows = load_data(str(f))
        assert len(rows) == 2

    def test_loads_dict_with_data_key(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"data": [{"id": 1}]}))
        rows = load_data(str(f))
        assert rows[0]["id"] == 1

    def test_loads_dict_with_records_key(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"records": [{"id": 1}]}))
        rows = load_data(str(f))
        assert len(rows) == 1

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_data(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_structure_exits(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"not_a_list_key": "value"}))
        with pytest.raises(SystemExit):
            load_data(str(f))


# ===========================================================================
# load_data — CSV
# ===========================================================================

class TestLoadDataCsv:

    def test_loads_csv_rows(self, tmp_path):
        f = tmp_path / "d.csv"
        f.write_text("id,name,age\n1,Alice,30\n2,Bob,25\n")
        rows = load_data(str(f))
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"

    def testcoerces_numeric_strings(self, tmp_path):
        f = tmp_path / "d.csv"
        f.write_text("id,salary\n1,50000\n")
        rows = load_data(str(f))
        assert isinstance(rows[0]["id"], int)
        assert isinstance(rows[0]["salary"], int)

    def test_empty_string_becomes_none(self, tmp_path):
        f = tmp_path / "d.csv"
        f.write_text("id,name\n1,\n")
        rows = load_data(str(f))
        assert rows[0]["name"] is None

    def test_unsupported_extension_exits(self, tmp_path):
        f = tmp_path / "d.xlsx"
        f.write_text("data")
        with pytest.raises(SystemExit):
            load_data(str(f))


# ===========================================================================
# coerce
# ===========================================================================

class TestCoerce:

    def test_integer_string(self):
        assert coerce("42") == 42

    def test_float_string(self):
        assert coerce("3.14") == 3.14

    def test_plain_string_unchanged(self):
        assert coerce("hello") == "hello"

    def test_empty_string_is_none(self):
        assert coerce("") is None

    def test_null_string_is_none(self):
        assert coerce("null") is None

    def test_none_string_is_none(self):
        assert coerce("none") is None

    def test_na_string_is_none(self):
        assert coerce("na") is None


# ===========================================================================
# load_config
# ===========================================================================

class TestLoadConfig:

    def test_returns_empty_dict_when_no_path(self):
        assert load_config(None) == {}

    def test_loads_valid_yaml(self, tmp_path):
        f = tmp_path / "cfg.yaml"
        f.write_text("pk_column: id\nexpected_min: 10\n")
        cfg = load_config(str(f))
        assert cfg["pk_column"] == "id"
        assert cfg["expected_min"] == 10

    def test_missing_config_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_config(str(tmp_path / "missing.yaml"))

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        cfg = load_config(str(f))
        assert cfg == {}


# ===========================================================================
# resolve_config
# ===========================================================================

class TestResolveConfig:

    def test_now_timestamp_becomes_datetime(self):
        cfg = resolve_config({"latest_timestamp": "now"})
        assert isinstance(cfg["latest_timestamp"], datetime)

    def test_iso_timestamp_becomes_datetime(self):
        cfg = resolve_config({"latest_timestamp": "2024-06-01T00:00:00"})
        assert isinstance(cfg["latest_timestamp"], datetime)

    def test_ranges_list_becomes_tuple(self):
        cfg = resolve_config({"ranges": {"age": [0, 120]}})
        assert cfg["ranges"]["age"] == (0, 120)

    def test_business_rules_expr_compiled_to_callables(self):
        cfg = resolve_config(
            {"business_rules_expr": {"salary_pos": "salary > 0"}})
        assert "rules" in cfg
        assert callable(cfg["rules"]["salary_pos"])
        assert cfg["rules"]["salary_pos"]({"salary": 100}) is True
        assert cfg["rules"]["salary_pos"]({"salary": -1}) is False

    def test_cross_rules_expr_compiled_to_callables(self):
        cfg = resolve_config({"cross_rules_expr": {"order": "end > start"}})
        assert "cross_rules" in cfg
        assert callable(cfg["cross_rules"]["order"])

    def test_unrelated_keys_passed_through(self):
        cfg = resolve_config({"pk_column": "id", "expected_min": 5})
        assert cfg["pk_column"] == "id"
        assert cfg["expected_min"] == 5


# ===========================================================================
# safe_eval_rule
# ===========================================================================

class TestSafeEvalRule:

    def test_greater_than(self):
        fn = safe_eval_rule("salary > 0")
        assert fn({"salary": 100}) is True
        assert fn({"salary": -1}) is False

    def test_equality(self):
        fn = safe_eval_rule("status == 'active'")
        assert fn({"status": "active"}) is True
        assert fn({"status": "inactive"}) is False

    def test_and_operator(self):
        fn = safe_eval_rule("salary > 0 and age >= 18")
        assert fn({"salary": 100, "age": 25}) is True
        assert fn({"salary": 100, "age": 10}) is False

    def test_or_operator(self):
        fn = safe_eval_rule("status == 'active' or status == 'pending'")
        assert fn({"status": "active"}) is True
        assert fn({"status": "deleted"}) is False

    def test_not_operator(self):
        fn = safe_eval_rule("not salary == 0")
        assert fn({"salary": 100}) is True
        assert fn({"salary": 0}) is False

    def test_exception_in_eval_returns_false(self):
        """Rule on a None value should return False, not raise."""
        fn = safe_eval_rule("salary > 0")
        assert fn({"salary": None}) is False
