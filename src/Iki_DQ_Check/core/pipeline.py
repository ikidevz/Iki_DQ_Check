from .base import DataCheck, CheckResult, Severity, QualityReport
from ..checks import (
    NullCheck,
    PrimaryKeyCheck,
    DuplicateRowCheck,
    DataTypeCheck,
    NumericRangeCheck,
    RegexCheck,
    DomainCheck,
    BusinessRuleCheck,
    CrossColumnCheck,
    FreshnessCheck,
    VolumeCheck,
    OutlierCheck,
    ReferentialIntegrityCheck,
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
    CompletenessCheck

)
from typing import Any

REGISTRY: dict[str, type[DataCheck]] = {
    # LITE
    "NullCheck":                    NullCheck,
    "PrimaryKeyCheck":              PrimaryKeyCheck,
    "DuplicateRowCheck":            DuplicateRowCheck,
    "DataTypeCheck":                DataTypeCheck,
    "NumericRangeCheck":            NumericRangeCheck,
    # STANDARD
    "RegexCheck":                   RegexCheck,
    "DomainCheck":                  DomainCheck,
    "BusinessRuleCheck":            BusinessRuleCheck,
    "CrossColumnCheck":             CrossColumnCheck,
    "FreshnessCheck":               FreshnessCheck,
    "VolumeCheck":                  VolumeCheck,
    "OutlierCheck":                 OutlierCheck,
    "ReferentialIntegrityCheck":    ReferentialIntegrityCheck,
    # ADVANCED
    "SchemaDriftCheck":             SchemaDriftCheck,
    "DuplicateFileIngestionCheck":  DuplicateFileIngestionCheck,
    "HierarchyCheck":               HierarchyCheck,
    "AuditColumnCheck":             AuditColumnCheck,
    "CrossSystemConsistencyCheck":  CrossSystemConsistencyCheck,
    "ReferenceDataCheck":           ReferenceDataCheck,
    "ChecksumCheck":                ChecksumCheck,
    "DistributionCheck":            DistributionCheck,
    "NegativeValueCheck":           NegativeValueCheck,
    "PercentageTotalCheck":         PercentageTotalCheck,
    "StringLengthCheck":            StringLengthCheck,
    "CompletenessCheck":            CompletenessCheck,
}

TIER_MAP: dict[str, list[str]] = {
    "lite":     ["NullCheck", "PrimaryKeyCheck", "DuplicateRowCheck",
                 "DataTypeCheck", "NumericRangeCheck"],
    "standard": ["RegexCheck", "DomainCheck", "BusinessRuleCheck", "CrossColumnCheck",
                 "FreshnessCheck", "VolumeCheck", "OutlierCheck", "ReferentialIntegrityCheck"],
    "advanced": ["SchemaDriftCheck", "DuplicateFileIngestionCheck", "HierarchyCheck",
                 "AuditColumnCheck", "CrossSystemConsistencyCheck", "ReferenceDataCheck",
                 "ChecksumCheck", "DistributionCheck", "NegativeValueCheck",
                 "PercentageTotalCheck", "StringLengthCheck", "CompletenessCheck"],
}


class DataQualityPipeline:
    """Orchestrates checks. Never raises — always returns QualityReport."""

    def __init__(self, name: str = "pipeline") -> None:
        self._name = name
        self._checks: list[DataCheck] = []

    def add(self, check: DataCheck) -> "DataQualityPipeline":
        self._checks.append(check)
        return self

    def run(self, data: Any, fail_fast: bool = False, tier: str | None = None, **kwargs: Any) -> QualityReport:
        results: list[CheckResult] = []

        # -----------------------------
        # EMPTY PIPELINE → EMPTY REPORT
        # -----------------------------
        if not self._checks:
            return QualityReport(self._name, [])

        # -----------------------------
        # EXECUTE CHECKS
        # -----------------------------
        for check in self._checks:
            try:
                result = check.run(data, **kwargs)
            except Exception as exc:
                result = CheckResult(
                    check.name,
                    check.tier,
                    False,
                    f"Unexpected error: {exc}",
                    Severity.CRITICAL
                )

            results.append(result)

            if fail_fast and not result.passed and result.severity == Severity.CRITICAL:
                break

        return QualityReport(self._name, results)
