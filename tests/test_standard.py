"""
test_standard.py — Unit tests for Standard tier checks (8 checks).

Checks covered:
    RegexCheck · DomainCheck · BusinessRuleCheck · CrossColumnCheck
    FreshnessCheck · VolumeCheck · OutlierCheck · ReferentialIntegrityCheck
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from conftest import assert_pass, assert_fail, assert_in_details

from Iki_DQ_Check import (
    RegexCheck,
    DomainCheck,
    BusinessRuleCheck,
    CrossColumnCheck,
    FreshnessCheck,
    VolumeCheck,
    OutlierCheck,
    ReferentialIntegrityCheck,
    CheckTier,
    Severity,
)

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ===========================================================================
# RegexCheck
# ===========================================================================

class TestRegexCheck:

    def test_detects_invalid_email(self):
        data = [{"email": "not-an-email"}]
        assert_fail(RegexCheck().run(data, patterns={"email": EMAIL_PATTERN}))

    def test_passes_valid_email(self):
        data = [{"email": "user@example.com"}]
        assert_pass(RegexCheck().run(data, patterns={"email": EMAIL_PATTERN}))

    def test_no_patterns_skips(self):
        data = [{"email": "garbage"}]
        assert_pass(RegexCheck().run(data))

    def test_severity_is_warning(self):
        assert RegexCheck().severity == Severity.WARNING

    def test_tier_is_standard(self):
        assert RegexCheck().tier == CheckTier.STANDARD

    def test_multiple_pattern_columns(self):
        data = [{"email": "bad", "phone": "also-bad"}]
        result = RegexCheck().run(data, patterns={
            "email": EMAIL_PATTERN,
            "phone": r"^\d{10}$",
        })
        assert_fail(result)
        assert len(result.details["violations"]) == 2


# ===========================================================================
# DomainCheck
# ===========================================================================

class TestDomainCheck:

    def test_detects_invalid_domain_value(self):
        data = [{"status": "deleted"}]
        assert_fail(DomainCheck().run(data, allowed={
                    "status": ["active", "inactive"]}))

    def test_passes_valid_domain_value(self):
        data = [{"status": "active"}]
        assert_pass(DomainCheck().run(data, allowed={
                    "status": ["active", "inactive"]}))

    def test_no_allowed_skips(self):
        data = [{"status": "whatever"}]
        assert_pass(DomainCheck().run(data))

    def test_case_sensitive_mismatch(self):
        data = [{"status": "Active"}]  # capital A
        assert_fail(DomainCheck().run(data, allowed={"status": ["active"]}))

    def test_violations_detail_populated(self):
        data = [{"status": "deleted"}]
        result = DomainCheck().run(data, allowed={"status": ["active"]})
        assert_fail(result)
        assert "status" in result.details["violations"]


# ===========================================================================
# BusinessRuleCheck
# ===========================================================================

class TestBusinessRuleCheck:

    def test_rule_fail(self):
        data = [{"salary": -100}]
        rules = {"salary_positive": lambda r: r["salary"] > 0}
        assert_fail(BusinessRuleCheck().run(data, rules=rules))

    def test_rule_pass(self):
        data = [{"salary": 5000}]
        rules = {"salary_positive": lambda r: r["salary"] > 0}
        assert_pass(BusinessRuleCheck().run(data, rules=rules))

    def test_exception_in_rule_treated_as_fail(self):
        """Rule that throws (e.g. TypeError on None) should count as failure."""
        data = [{"salary": None}]
        rules = {"bad_rule": lambda r: r["salary"] > 0}
        assert_fail(BusinessRuleCheck().run(data, rules=rules))

    def test_no_rules_skips(self):
        assert_pass(BusinessRuleCheck().run([{"salary": -1}]))

    def test_multiple_rules_one_fails(self):
        data = [{"salary": 5000, "name": ""}]
        rules = {
            "salary_positive": lambda r: r["salary"] > 0,
            "name_not_empty": lambda r: r["name"] != "",
        }
        assert_fail(BusinessRuleCheck().run(data, rules=rules))

    def test_violations_detail_populated(self):
        data = [{"salary": -1}]
        rules = {"must_be_positive": lambda r: r["salary"] > 0}
        result = BusinessRuleCheck().run(data, rules=rules)
        assert_fail(result)
        assert "violations" in result.details


# ===========================================================================
# CrossColumnCheck
# ===========================================================================

class TestCrossColumnCheck:

    def test_end_before_start_fails(self):
        data = [{"start": 10, "end": 5}]
        rules = {"order": lambda r: r["end"] > r["start"]}
        assert_fail(CrossColumnCheck().run(data, cross_rules=rules))

    def test_valid_order_passes(self):
        data = [{"start": 1, "end": 10}]
        rules = {"order": lambda r: r["end"] > r["start"]}
        assert_pass(CrossColumnCheck().run(data, cross_rules=rules))

    def test_no_cross_rules_skips(self):
        data = [{"start": 10, "end": 1}]
        assert_pass(CrossColumnCheck().run(data))

    def test_multi_column_rule(self):
        data = [{"discount": 50, "price": 30}]  # discount > price
        rules = {"discount_valid": lambda r: r["discount"] < r["price"]}
        assert_fail(CrossColumnCheck().run(data, cross_rules=rules))


# ===========================================================================
# FreshnessCheck
# ===========================================================================

class TestFreshnessCheck:

    def test_stale_data_fails(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=5)
        assert_fail(FreshnessCheck().run(
            [], latest_timestamp=ts, max_delay_hours=2.0))

    def test_fresh_data_passes(self):
        ts = datetime.now(timezone.utc) - timedelta(minutes=30)
        assert_pass(FreshnessCheck().run(
            [], latest_timestamp=ts, max_delay_hours=2.0))

    def test_no_timestamp_skips(self):
        assert_pass(FreshnessCheck().run([]))

    def test_exactly_at_boundary_passes(self):
        """Data exactly 2 hours old with a 2-hour limit should pass."""
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        assert_pass(FreshnessCheck().run(
            [], latest_timestamp=ts, max_delay_hours=2.0))

    def test_delay_details_populated(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=10)
        result = FreshnessCheck().run([], latest_timestamp=ts, max_delay_hours=1.0)
        assert_fail(result)
        assert "delay_hours" in result.details


# ===========================================================================
# VolumeCheck
# ===========================================================================

class TestVolumeCheck:

    def test_too_few_rows_fails(self):
        data = [{"id": 1}]
        assert_fail(VolumeCheck().run(data, expected_min=10, expected_max=100))

    def test_too_many_rows_fails(self):
        data = [{"id": i} for i in range(200)]
        assert_fail(VolumeCheck().run(data, expected_min=1, expected_max=100))

    def test_within_range_passes(self):
        data = [{"id": i} for i in range(50)]
        assert_pass(VolumeCheck().run(data, expected_min=10, expected_max=100))

    def test_no_bounds_skips(self):
        assert_pass(VolumeCheck().run([]))

    def test_exact_min_passes(self):
        data = [{"id": i} for i in range(10)]
        assert_pass(VolumeCheck().run(data, expected_min=10, expected_max=100))

    def test_exact_max_passes(self):
        data = [{"id": i} for i in range(100)]
        assert_pass(VolumeCheck().run(data, expected_min=10, expected_max=100))


# ===========================================================================
# OutlierCheck
# ===========================================================================

class TestOutlierCheck:

    def test_detects_spike(self):
        data = [{"salary": v}
                for v in [50000, 51000, 49000, 52000, 48000, 500000]]
        assert_fail(OutlierCheck().run(data, columns=["salary"]))

    def test_no_outliers_passes(self):
        data = [{"salary": v} for v in [50000, 51000, 49000, 52000, 48000]]
        assert_pass(OutlierCheck().run(data, columns=["salary"]))

    def test_no_columns_skips(self):
        assert_pass(OutlierCheck().run([{"salary": 999999}]))

    def test_outlier_details_populated(self):
        data = [{"salary": v} for v in [1, 2, 2, 2, 2, 1000000]]
        result = OutlierCheck().run(data, columns=["salary"])
        assert_fail(result)
        assert "outliers" in result.details

    def test_severity_is_warning(self):
        assert OutlierCheck().severity == Severity.WARNING


# ===========================================================================
# ReferentialIntegrityCheck
# ===========================================================================

class TestReferentialIntegrityCheck:

    def test_orphaned_fk_fails(self):
        data = [{"dept_id": 9}]
        assert_fail(ReferentialIntegrityCheck().run(
            data, fk_column="dept_id", reference_values=[1, 2, 3]))

    def test_valid_fk_passes(self):
        data = [{"dept_id": 1}, {"dept_id": 2}]
        assert_pass(ReferentialIntegrityCheck().run(
            data, fk_column="dept_id", reference_values=[1, 2, 3]))

    def test_null_fk_not_counted_as_violation(self):
        """None FK values should not count as orphans."""
        data = [{"dept_id": None}]
        assert_pass(ReferentialIntegrityCheck().run(
            data, fk_column="dept_id", reference_values=[1, 2, 3]))

    def test_no_fk_config_skips(self):
        data = [{"dept_id": 999}]
        assert_pass(ReferentialIntegrityCheck().run(data))

    def test_violations_detail_populated(self):
        data = [{"dept_id": 99}]
        result = ReferentialIntegrityCheck().run(
            data, fk_column="dept_id", reference_values=[1, 2])
        assert_fail(result)
        assert "violations" in result.details
