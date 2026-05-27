"""
test_pipeline.py — Unit tests for DataQualityPipeline and QualityReport.

Covers: pipeline orchestration, fail-fast, error handling, success rate,
        JSON serialization, and QualityReport properties.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from conftest import assert_pass, assert_fail, SAMPLE_DATA, SINGLE_ROW, EMPTY_DATA

from Iki_DQ_Check import (
    DataQualityPipeline,
    NullCheck,
    PrimaryKeyCheck,
    DuplicateRowCheck,
    NumericRangeCheck,
    CheckTier,
    Severity,
)


# ===========================================================================
# Pipeline orchestration
# ===========================================================================

class TestPipelineOrchestration:

    def test_runs_all_added_checks(self):
        report = (
            DataQualityPipeline("test")
            .add(NullCheck())
            .add(PrimaryKeyCheck())
            .run(SAMPLE_DATA, pk_column="id")
        )
        assert len(report.results) == 2

    def test_add_returns_pipeline_for_chaining(self):
        pipeline = DataQualityPipeline("chain")
        result = pipeline.add(NullCheck())
        assert result is pipeline

    def test_empty_pipeline_returns_empty_report(self):
        report = DataQualityPipeline("empty").run(SAMPLE_DATA)
        assert len(report.results) == 0

    def test_pipeline_name_is_preserved(self):
        report = DataQualityPipeline("my_pipeline").add(
            NullCheck()).run(SAMPLE_DATA)
        assert report.pipeline_name == "my_pipeline"

    def test_ran_at_is_set(self):
        report = DataQualityPipeline("ts_test").add(
            NullCheck()).run(SAMPLE_DATA)
        assert report.ran_at is not None


# ===========================================================================
# Fail-fast behaviour
# ===========================================================================

class TestFailFast:

    def test_stops_after_first_critical_failure(self):
        data = [{"id": None}]   # PK will fail CRITICAL → stop
        pipeline = (
            DataQualityPipeline("failfast")
            .add(PrimaryKeyCheck())
            .add(NullCheck())
            .add(DuplicateRowCheck())
        )
        report = pipeline.run(data, fail_fast=True, pk_column="id")
        assert len(report.results) == 1

    def test_fail_fast_false_runs_all_checks(self):
        data = [{"id": None}]
        pipeline = (
            DataQualityPipeline("nofailfast")
            .add(PrimaryKeyCheck())
            .add(NullCheck())
            .add(DuplicateRowCheck())
        )
        report = pipeline.run(data, fail_fast=False, pk_column="id")
        assert len(report.results) == 3


# ===========================================================================
# Error resilience
# ===========================================================================

class TestErrorResilience:

    def test_never_raises_on_buggy_check(self):
        class BrokenCheck(NullCheck):
            def run(self, data, **_):
                raise RuntimeError("something went wrong")

        report = DataQualityPipeline("safe").add(BrokenCheck()).run([])
        assert len(report.results) == 1
        assert not report.results[0].passed
        assert "Unexpected error" in report.results[0].message

    def test_broken_check_result_is_critical(self):
        class BrokenCheck(NullCheck):
            def run(self, data, **_):
                raise ValueError("oops")

        report = DataQualityPipeline("safe").add(BrokenCheck()).run([])
        assert report.results[0].severity == Severity.CRITICAL


# ===========================================================================
# QualityReport properties
# ===========================================================================

class TestQualityReport:

    def _clean_report(self):
        return (
            DataQualityPipeline("rate_test")
            .add(NullCheck())
            .add(PrimaryKeyCheck())
            .run(SAMPLE_DATA, pk_column="id")
        )

    def test_success_rate_all_pass(self):
        report = self._clean_report()
        assert report.success_rate == 1.0

    def test_passed_and_failed_lists(self):
        report = self._clean_report()
        assert len(report.passed) == 2
        assert len(report.failed) == 0

    def test_summary_contains_pipeline_name(self):
        report = DataQualityPipeline("smoke").add(NullCheck()).run(SAMPLE_DATA)
        assert "smoke" in report.summary()

    def test_summary_contains_pass_icon(self):
        report = DataQualityPipeline("icons").add(NullCheck()).run(SAMPLE_DATA)
        assert "✅" in report.summary()

    def test_summary_contains_pass_rate(self):
        report = DataQualityPipeline("pr").add(NullCheck()).run(SAMPLE_DATA)
        assert "Pass rate" in report.summary()

    def test_to_dict_is_json_serializable(self):
        report = DataQualityPipeline("json_test").add(
            NullCheck()).run(SAMPLE_DATA)
        serialized = json.dumps(report.to_dict(), default=str)
        assert "json_test" in serialized

    def test_to_dict_structure(self):
        report = DataQualityPipeline("dict_test").add(
            NullCheck()).run(SAMPLE_DATA)
        d = report.to_dict()
        for key in ("pipeline_name", "ran_at", "success_rate", "total", "passed", "failed", "results"):
            assert key in d, f"Missing key: {key}"

    def test_success_rate_with_failure(self):
        data = [{"id": None}]
        report = DataQualityPipeline("fail").add(PrimaryKeyCheck()).add(NullCheck()).run(
            data, pk_column="id")
        assert 0.0 <= report.success_rate < 1.0


# ===========================================================================
# CheckResult immutability
# ===========================================================================

class TestCheckResultImmutability:

    def test_check_result_is_frozen(self):
        result = NullCheck().run(SINGLE_ROW)
        assert dataclasses.is_dataclass(result)
        with pytest.raises(Exception):
            result.passed = False  # type: ignore  # should raise FrozenInstanceError


# ===========================================================================
# Edge cases: empty and single-row datasets
# ===========================================================================

class TestEdgeCasePipelines:

    def test_empty_dataset_runs_without_error(self):
        report = (
            DataQualityPipeline("empty")
            .add(NullCheck())
            .add(PrimaryKeyCheck())
            .add(DuplicateRowCheck())
            .run(EMPTY_DATA)
        )
        assert len(report.results) == 3

    def test_single_row_all_pass(self):
        data = [{"id": 1, "salary": 50000}]
        report = (
            DataQualityPipeline("single")
            .add(NullCheck())
            .add(PrimaryKeyCheck())
            .add(NumericRangeCheck())
            .run(data, pk_column="id", ranges={"salary": (0, None)})
        )
        assert all(r.passed for r in report.results)
