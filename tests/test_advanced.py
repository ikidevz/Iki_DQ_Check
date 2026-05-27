"""
test_advanced.py — Unit tests for Advanced tier checks (12 checks).

Checks covered:
    SchemaDriftCheck · DuplicateFileIngestionCheck · HierarchyCheck
    AuditColumnCheck · CrossSystemConsistencyCheck · ReferenceDataCheck
    ChecksumCheck · DistributionCheck · NegativeValueCheck
    PercentageTotalCheck · StringLengthCheck · CompletenessCheck
"""

from __future__ import annotations

import pytest
from conftest import assert_pass, assert_fail


from Iki_DQ_Check import (
    SchemaDriftCheck,
    DuplicateFileIngestionCheck,
    HierarchyCheck,
    AuditColumnCheck,
    CrossSystemConsistencyCheck,
    ReferenceDataCheck,
    ChecksumCheck,
    DistributionCheck,
    NegativeValueCheck,
    PercentageTotalCheck,
    StringLengthCheck,
    CompletenessCheck,
    CheckTier,
    Severity,
)


# ===========================================================================
# SchemaDriftCheck
# ===========================================================================

class TestSchemaDriftCheck:

    def test_detects_added_column(self):
        data = [{"id": 1, "name": "Alice", "new_col": "surprise"}]
        result = SchemaDriftCheck().run(data, expected_columns=["id", "name"])
        assert_fail(result)
        assert "new_col" in result.details["added"]

    def test_detects_removed_column(self):
        data = [{"id": 1}]
        result = SchemaDriftCheck().run(data, expected_columns=["id", "name"])
        assert_fail(result)
        assert "name" in result.details["removed"]

    def test_exact_schema_match_passes(self):
        data = [{"id": 1, "name": "Alice"}]
        assert_pass(SchemaDriftCheck().run(
            data, expected_columns=["id", "name"]))

    def test_no_expected_columns_skips(self):
        data = [{"id": 1, "surprise": True}]
        assert_pass(SchemaDriftCheck().run(data))

    def test_tier_is_advanced(self):
        assert SchemaDriftCheck().tier == CheckTier.ADVANCED


# ===========================================================================
# DuplicateFileIngestionCheck
# ===========================================================================

class TestDuplicateFileIngestionCheck:

    def test_detects_repeated_file(self):
        data = [{"file_name": "data.csv"}, {"file_name": "data.csv"}]
        assert_fail(DuplicateFileIngestionCheck().run(data))

    def test_unique_files_pass(self):
        data = [{"file_name": "a.csv"}, {"file_name": "b.csv"}]
        assert_pass(DuplicateFileIngestionCheck().run(data))

    def test_empty_data_passes(self):
        assert_pass(DuplicateFileIngestionCheck().run([]))


# ===========================================================================
# HierarchyCheck
# ===========================================================================

class TestHierarchyCheck:

    HIERARCHY = {"Asia": ["Japan", "India", "China"],
                 "Europe": ["Germany", "France", "UK"]}

    def test_invalid_child_fails(self):
        data = [{"region": "Asia", "country": "Canada"}]
        assert_fail(HierarchyCheck().run(
            data,
            parent_column="region",
            child_column="country",
            valid_hierarchy=self.HIERARCHY,
        ))

    def test_valid_child_passes(self):
        data = [{"region": "Asia", "country": "Japan"}]
        assert_pass(HierarchyCheck().run(
            data,
            parent_column="region",
            child_column="country",
            valid_hierarchy=self.HIERARCHY,
        ))

    def test_unknown_parent_fails(self):
        data = [{"region": "MiddleEarth", "country": "Shire"}]
        assert_fail(HierarchyCheck().run(
            data,
            parent_column="region",
            child_column="country",
            valid_hierarchy=self.HIERARCHY,
        ))

    def test_no_hierarchy_config_skips(self):
        data = [{"region": "Asia", "country": "Canada"}]
        assert_pass(HierarchyCheck().run(data))


# ===========================================================================
# AuditColumnCheck
# ===========================================================================

class TestAuditColumnCheck:

    def test_missing_created_by_fails(self):
        data = [{"created_by": None, "created_at": "2024-01-01"}]
        assert_fail(AuditColumnCheck().run(
            data, audit_columns=["created_by", "created_at"]))

    def test_all_audit_columns_populated_passes(self):
        data = [{"created_by": "system", "created_at": "2024-01-01"}]
        assert_pass(AuditColumnCheck().run(
            data, audit_columns=["created_by", "created_at"]))

    def test_missing_column_key_fails(self):
        """Row that doesn't even have the audit column key should fail."""
        data = [{"name": "Alice"}]
        assert_fail(AuditColumnCheck().run(data, audit_columns=["created_by"]))

    def test_no_audit_columns_skips(self):
        data = [{"created_by": None}]
        assert_pass(AuditColumnCheck().run(data))


# ===========================================================================
# CrossSystemConsistencyCheck
# ===========================================================================

class TestCrossSystemConsistencyCheck:

    def test_count_mismatch_fails(self):
        assert_fail(CrossSystemConsistencyCheck().run(
            [], source_count=1000, target_count=800, tolerance_pct=0.1))

    def test_within_tolerance_passes(self):
        assert_pass(CrossSystemConsistencyCheck().run(
            [], source_count=1000, target_count=995, tolerance_pct=0.1))

    def test_exact_match_passes(self):
        assert_pass(CrossSystemConsistencyCheck().run(
            [], source_count=500, target_count=500))

    def test_no_counts_skips(self):
        assert_pass(CrossSystemConsistencyCheck().run([]))

    def test_details_populated_on_fail(self):
        result = CrossSystemConsistencyCheck().run(
            [], source_count=1000, target_count=500, tolerance_pct=0.1)
        assert_fail(result)
        assert "source_count" in result.details


# ===========================================================================
# ReferenceDataCheck
# ===========================================================================

class TestReferenceDataCheck:

    def test_unknown_code_fails(self):
        data = [{"status": "DELETED"}]
        assert_fail(ReferenceDataCheck().run(
            data, code_column="status", valid_codes=["active", "inactive"]))

    def test_valid_code_passes(self):
        data = [{"status": "active"}]
        assert_pass(ReferenceDataCheck().run(
            data, code_column="status", valid_codes=["active", "inactive"]))

    def test_no_code_column_skips(self):
        data = [{"status": "UNKNOWN"}]
        assert_pass(ReferenceDataCheck().run(data))

    def test_violations_detail_populated(self):
        data = [{"status": "BAD"}]
        result = ReferenceDataCheck().run(
            data, code_column="status", valid_codes=["active"])
        assert_fail(result)
        assert "violations" in result.details


# ===========================================================================
# ChecksumCheck
# ===========================================================================

class TestChecksumCheck:

    def test_hash_mismatch_fails(self):
        assert_fail(ChecksumCheck().run(
            [], source_payload="abc", target_payload="xyz"))

    def test_identical_payloads_pass(self):
        assert_pass(ChecksumCheck().run(
            [], source_payload="same", target_payload="same"))

    def test_no_payload_skips(self):
        assert_pass(ChecksumCheck().run([]))

    def test_details_contain_hashes(self):
        result = ChecksumCheck().run([], source_payload="a", target_payload="b")
        assert_fail(result)
        assert "source_hash" in result.details
        assert "target_hash" in result.details


# ===========================================================================
# DistributionCheck
# ===========================================================================

class TestDistributionCheck:

    def test_computes_stats_and_passes(self):
        data = [{"salary": v} for v in [40000, 50000, 60000, 45000, 55000]]
        result = DistributionCheck().run(data, columns=["salary"])
        assert_pass(result)
        assert "distribution" in result.details
        assert "salary" in result.details["distribution"]
        assert result.details["distribution"]["salary"]["mean"] == 50000.0

    def test_no_columns_skips(self):
        assert_pass(DistributionCheck().run([{"salary": 999}]))

    def test_severity_is_info(self):
        assert DistributionCheck().severity == Severity.INFO

    def test_stats_keys_present(self):
        data = [{"val": v} for v in [1, 2, 3, 4, 5]]
        result = DistributionCheck().run(data, columns=["val"])
        dist = result.details["distribution"]["val"]
        assert "mean" in dist
        assert "median" in dist
        assert "stdev" in dist


# ===========================================================================
# NegativeValueCheck
# ===========================================================================

class TestNegativeValueCheck:

    def test_negative_value_fails(self):
        data = [{"quantity": -5}]
        assert_fail(NegativeValueCheck().run(data, columns=["quantity"]))

    def test_zero_is_allowed(self):
        data = [{"quantity": 0}]
        assert_pass(NegativeValueCheck().run(data, columns=["quantity"]))

    def test_positive_passes(self):
        data = [{"quantity": 10}]
        assert_pass(NegativeValueCheck().run(data, columns=["quantity"]))

    def test_no_columns_skips(self):
        data = [{"quantity": -999}]
        assert_pass(NegativeValueCheck().run(data))

    def test_violations_detail_populated(self):
        data = [{"qty": -3}]
        result = NegativeValueCheck().run(data, columns=["qty"])
        assert_fail(result)
        assert "violations" in result.details


# ===========================================================================
# PercentageTotalCheck
# ===========================================================================

class TestPercentageTotalCheck:

    def test_does_not_sum_to_100_fails(self):
        data = [{"pct": 40}, {"pct": 30}, {"pct": 20}]  # sums to 90
        assert_fail(PercentageTotalCheck().run(data, percentage_column="pct"))

    def test_sums_to_100_passes(self):
        data = [{"pct": 40}, {"pct": 30}, {"pct": 30}]
        assert_pass(PercentageTotalCheck().run(data, percentage_column="pct"))

    def test_no_percentage_column_skips(self):
        data = [{"pct": 50}]
        assert_pass(PercentageTotalCheck().run(data))

    def test_within_tolerance_passes(self):
        data = [{"pct": 33.333}, {"pct": 33.333}, {"pct": 33.334}]
        assert_pass(PercentageTotalCheck().run(
            data, percentage_column="pct", tolerance=0.01))

    def test_severity_is_warning(self):
        assert PercentageTotalCheck().severity == Severity.WARNING


# ===========================================================================
# StringLengthCheck
# ===========================================================================

class TestStringLengthCheck:

    def test_too_long_fails(self):
        data = [{"name": "A" * 100}]
        assert_fail(StringLengthCheck().run(
            data, length_rules={"name": [1, 50]}))

    def test_empty_string_fails_when_min_is_1(self):
        data = [{"name": ""}]
        assert_fail(StringLengthCheck().run(
            data, length_rules={"name": [1, 50]}))

    def test_valid_string_passes(self):
        data = [{"name": "Alice"}]
        assert_pass(StringLengthCheck().run(
            data, length_rules={"name": [1, 50]}))

    def test_no_length_rules_skips(self):
        data = [{"name": "A" * 500}]
        assert_pass(StringLengthCheck().run(data))

    def test_exact_boundaries_pass(self):
        """Strings at exactly min and max length should pass."""
        data = [{"name": "A"}, {"name": "A" * 50}]
        assert_pass(StringLengthCheck().run(
            data, length_rules={"name": [1, 50]}))


# ===========================================================================
# CompletenessCheck
# ===========================================================================

class TestCompletenessCheck:

    def test_missing_partition_fails(self):
        data = [{"date": "2024-01-01"}, {"date": "2024-01-02"}]
        result = CompletenessCheck().run(
            data,
            partition_column="date",
            expected_partitions=["2024-01-01", "2024-01-02", "2024-01-03"],
        )
        assert_fail(result)
        assert "2024-01-03" in result.details["missing"]

    def test_all_partitions_present_passes(self):
        data = [{"date": "2024-01-01"}, {"date": "2024-01-02"}]
        assert_pass(CompletenessCheck().run(
            data,
            partition_column="date",
            expected_partitions=["2024-01-01", "2024-01-02"],
        ))

    def test_no_partition_config_skips(self):
        data = [{"date": "2024-01-01"}]
        assert_pass(CompletenessCheck().run(data))

    def test_severity_is_critical(self):
        assert CompletenessCheck().severity == Severity.CRITICAL

    def test_multiple_missing_partitions_reported(self):
        data = [{"dept": "Eng"}]
        result = CompletenessCheck().run(
            data,
            partition_column="dept",
            expected_partitions=["Eng", "HR", "Fin"],
        )
        assert_fail(result)
        assert len(result.details["missing"]) == 2
