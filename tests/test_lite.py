"""
test_lite.py — Unit tests for Lite tier checks (5 checks).

Checks covered:
    NullCheck · PrimaryKeyCheck · DuplicateRowCheck · DataTypeCheck · NumericRangeCheck
"""

from __future__ import annotations

import pytest
from conftest import assert_pass, assert_fail

from Iki_DQ_Check import (
    NullCheck,
    PrimaryKeyCheck,
    DuplicateRowCheck,
    DataTypeCheck,
    NumericRangeCheck,
    CheckTier,
    Severity,
)


# ===========================================================================
# NullCheck
# ===========================================================================

class TestNullCheck:

    def test_detects_none_value(self):
        data = [{"id": 1, "name": None}]
        assert_fail(NullCheck().run(data, columns=["name"]))

    def test_passes_clean_data(self):
        data = [{"id": 1, "name": "Alice"}]
        assert_pass(NullCheck().run(data))

    def test_ignores_unchecked_column(self):
        """Null in a column not in `columns` should not trigger failure."""
        data = [{"id": 1, "name": None, "age": 30}]
        assert_pass(NullCheck().run(data, columns=["age"]))

    def test_reports_multiple_null_columns(self):
        data = [{"a": None, "b": None, "c": 1}]
        result = NullCheck().run(data, columns=["a", "b", "c"])
        assert_fail(result)
        assert len(result.details["null_columns"]) == 2

    def test_severity_is_critical(self):
        assert NullCheck().severity == Severity.CRITICAL

    def test_tier_is_lite(self):
        assert NullCheck().tier == CheckTier.LITE


# ===========================================================================
# PrimaryKeyCheck
# ===========================================================================

class TestPrimaryKeyCheck:

    def test_detects_duplicate_pk(self):
        data = [{"id": 1}, {"id": 1}]
        assert_fail(PrimaryKeyCheck().run(data, pk_column="id"))

    def test_detects_null_pk(self):
        data = [{"id": None}]
        result = PrimaryKeyCheck().run(data, pk_column="id")
        assert_fail(result)
        assert result.details["null_pks"] == 1

    def test_passes_unique_keys(self):
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        assert_pass(PrimaryKeyCheck().run(data, pk_column="id"))

    def test_default_pk_column_is_id(self):
        """When pk_column is omitted it defaults to 'id'."""
        data = [{"id": 1}, {"id": 1}]
        assert_fail(PrimaryKeyCheck().run(data))

    def test_duplicate_details_populated(self):
        data = [{"id": 5}, {"id": 5}]
        result = PrimaryKeyCheck().run(data, pk_column="id")
        assert_fail(result)
        assert 5 in result.details["duplicate_values"]


# ===========================================================================
# DuplicateRowCheck
# ===========================================================================

class TestDuplicateRowCheck:

    def test_detects_fully_identical_rows(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 1, "name": "Alice"}]
        assert_fail(DuplicateRowCheck().run(data))

    def test_passes_unique_rows(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        assert_pass(DuplicateRowCheck().run(data))

    def test_key_columns_subset_pass(self):
        """Rows differ on 'ts' so key_columns=['id','name','ts'] should pass."""
        data = [
            {"id": 1, "name": "Alice", "ts": "a"},
            {"id": 1, "name": "Alice", "ts": "b"},
        ]
        assert_pass(DuplicateRowCheck().run(
            data, key_columns=["id", "name", "ts"]))

    def test_key_columns_subset_fail(self):
        """Same rows on ['id','name'] should fail."""
        data = [
            {"id": 1, "name": "Alice", "ts": "a"},
            {"id": 1, "name": "Alice", "ts": "b"},
        ]
        assert_fail(DuplicateRowCheck().run(data, key_columns=["id", "name"]))

    def test_three_identical_rows(self):
        data = [{"x": 1}] * 3
        assert_fail(DuplicateRowCheck().run(data))


# ===========================================================================
# DataTypeCheck
# ===========================================================================

class TestDataTypeCheck:

    def test_detects_invalid_int(self):
        data = [{"age": "thirty"}]
        assert_fail(DataTypeCheck().run(data, schema={"age": "int"}))

    def test_passes_valid_cast(self):
        data = [{"age": "30"}, {"age": 25}]
        assert_pass(DataTypeCheck().run(data, schema={"age": "int"}))

    def test_no_schema_skips(self):
        """Without a schema, the check should pass without inspecting data."""
        data = [{"age": "banana"}]
        assert_pass(DataTypeCheck().run(data))

    def test_null_values_skipped_in_type_check(self):
        """None values should not count as type violations."""
        data = [{"age": None}]
        assert_pass(DataTypeCheck().run(data, schema={"age": "int"}))

    def test_float_column(self):
        data = [{"salary": "not-a-float"}]
        assert_fail(DataTypeCheck().run(data, schema={"salary": "float"}))

    def test_violations_detail_populated(self):
        data = [{"age": "bad"}]
        result = DataTypeCheck().run(data, schema={"age": "int"})
        assert_fail(result)
        assert "age" in result.details["violations"]


# ===========================================================================
# NumericRangeCheck
# ===========================================================================

class TestNumericRangeCheck:

    def test_detects_value_above_max(self):
        data = [{"age": 200}]
        assert_fail(NumericRangeCheck().run(data, ranges={"age": (0, 120)}))

    def test_detects_negative_when_min_is_zero(self):
        data = [{"salary": -100}]
        assert_fail(NumericRangeCheck().run(
            data, ranges={"salary": (0, None)}))

    def test_passes_valid_values(self):
        data = [{"age": 30}, {"age": 45}]
        assert_pass(NumericRangeCheck().run(data, ranges={"age": (0, 120)}))

    def test_no_ranges_skips(self):
        data = [{"age": 999}]
        assert_pass(NumericRangeCheck().run(data))

    def test_none_min_allows_negatives(self):
        data = [{"temp": -50}]
        assert_pass(NumericRangeCheck().run(
            data, ranges={"temp": (None, 100)}))

    def test_boundary_values_pass(self):
        """Exact min and max should pass."""
        data = [{"age": 0}, {"age": 120}]
        assert_pass(NumericRangeCheck().run(data, ranges={"age": (0, 120)}))

    def test_violations_detail_populated(self):
        data = [{"age": 200}]
        result = NumericRangeCheck().run(data, ranges={"age": (0, 120)})
        assert_fail(result)
        assert "age" in result.details["violations"]
