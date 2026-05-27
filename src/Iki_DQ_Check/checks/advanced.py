from ..core import DataCheck, CheckTier, CheckResult, Severity
from typing import Any

import statistics
import hashlib


class SchemaDriftCheck(DataCheck):
    """Detect new, removed, or renamed columns vs expected schema."""
    tier = CheckTier.ADVANCED
    severity = Severity.CRITICAL

    def run(self, data: list[dict], expected_columns: list[str] | None = None, **_) -> CheckResult:
        if not data or not expected_columns:
            return self._pass("No data or schema to compare — skipped")
        actual = set(data[0].keys())
        expected = set(expected_columns)
        added, removed = actual - expected, expected - actual
        if added or removed:
            return self._fail("Schema drift detected",
                              added=list(added), removed=list(removed))
        return self._pass("Schema matches expected structure")


class DuplicateFileIngestionCheck(DataCheck):
    """Detect same file ingested more than once."""
    tier = CheckTier.ADVANCED
    severity = Severity.CRITICAL

    def run(self, data: list[dict], file_name_column: str = "file_name", **_) -> CheckResult:
        seen: dict[str, list] = {}
        for idx, row in enumerate(data):
            key = row.get(file_name_column)
            if key:
                seen.setdefault(key, []).append(idx)
        dupes = {f: rows for f, rows in seen.items() if len(rows) > 1}
        if dupes:
            return self._fail(f"{len(dupes)} file(s) ingested multiple times",
                              duplicated_files=list(dupes.keys()))
        return self._pass("No duplicate file ingestions found")


class HierarchyCheck(DataCheck):
    """Validate parent→child hierarchy relationships."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    def run(self, data: list[dict], parent_column: str | None = None,
            child_column: str | None = None,
            valid_hierarchy: dict[str, list[str]] | None = None, **_) -> CheckResult:
        if not parent_column or not child_column or not valid_hierarchy:
            return self._pass("No hierarchy config provided — skipped")
        violations = []
        for idx, row in enumerate(data):
            parent, child = row.get(parent_column), row.get(child_column)
            if parent and child:
                allowed = set(valid_hierarchy.get(parent, []))
                if child not in allowed:
                    violations.append(
                        {parent_column: parent, child_column: child, "row": idx})
        if violations:
            return self._fail(f"{len(violations)} hierarchy violation(s)",
                              violations=violations[:10])
        return self._pass("Hierarchy relationships are valid")


class AuditColumnCheck(DataCheck):
    """Verify audit columns (created_by, updated_at, etc.) are populated."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    DEFAULT = ["created_by", "created_at", "updated_by", "updated_at"]

    def run(self, data: list[dict], audit_columns: list[str] | None = None, **_) -> CheckResult:
        using_defaults = audit_columns is None
        cols = audit_columns or self.DEFAULT
        if not data:
            return self._pass("No data to check — skipped")
        if using_defaults:
            # Only run when ALL default audit columns are present in the schema
            schema_cols = set(data[0].keys())
            if not all(c in schema_cols for c in cols):
                return self._pass("No audit columns present in schema — skipped")
        missing: dict[str, list[int]] = {}
        for idx, row in enumerate(data):
            for col in cols:
                if row.get(col) is None:
                    missing.setdefault(col, []).append(idx)
        if missing:
            return self._fail(f"Audit columns missing in {len(missing)} column(s)",
                              missing=missing)
        return self._pass("Audit columns are fully populated")


class CrossSystemConsistencyCheck(DataCheck):
    """Validate row counts between source and target."""
    tier = CheckTier.ADVANCED
    severity = Severity.CRITICAL

    def run(self, data: Any, source_count: int | None = None,
            target_count: int | None = None, tolerance_pct: float = 0.1, **_) -> CheckResult:
        if source_count is None or target_count is None:
            return self._pass("No counts provided — skipped")
        diff_pct = abs(source_count - target_count) / max(source_count, 1)
        if diff_pct > tolerance_pct:
            return self._fail(
                f"Count mismatch: source={source_count}, target={target_count} ({diff_pct:.1%})",
                source_count=source_count, target_count=target_count, diff_pct=round(diff_pct, 4))
        return self._pass(f"Counts consistent ({diff_pct:.1%} diff)")


class ReferenceDataCheck(DataCheck):
    """Ensure reference/master data codes are known."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    def run(self, data: list[dict], code_column: str | None = None,
            valid_codes: list[str] | None = None, **_) -> CheckResult:
        if not code_column or valid_codes is None:
            return self._pass("No reference config provided — skipped")
        valid_set = set(valid_codes)
        unknown = [{"row": i, "code": r.get(code_column)}
                   for i, r in enumerate(data) if r.get(code_column) not in valid_set]
        if unknown:
            return self._fail(f"{len(unknown)} unknown code(s) in '{code_column}'",
                              violations=unknown[:10])
        return self._pass("All reference codes are valid")


class ChecksumCheck(DataCheck):
    """Compare SHA-256 hashes between source and target payloads."""
    tier = CheckTier.ADVANCED
    severity = Severity.CRITICAL

    @staticmethod
    def _hash(payload: str) -> str:
        return hashlib.sha256(payload.encode()).hexdigest()

    def run(self, data: Any, source_payload: str | None = None,
            target_payload: str | None = None, **_) -> CheckResult:
        if source_payload is None or target_payload is None:
            return self._pass("No payloads provided — skipped")
        src, tgt = self._hash(source_payload), self._hash(target_payload)
        if src != tgt:
            return self._fail("Checksum mismatch", source_hash=src, target_hash=tgt)
        return self._pass(f"Checksum matches: {src[:12]}…")


class DistributionCheck(DataCheck):
    """Compute mean / median / stddev for numeric columns."""
    tier = CheckTier.ADVANCED
    severity = Severity.INFO

    def run(self, data: list[dict], columns: list[str] | None = None, **_) -> CheckResult:
        if not columns:
            return self._pass("No columns specified — skipped")
        stats: dict[str, dict] = {}
        for col in columns:
            vals = [float(r[col]) for r in data if r.get(col) is not None]
            if not vals:
                continue
            stats[col] = {
                "count":  len(vals),
                "mean":   round(statistics.mean(vals), 2),
                "median": round(statistics.median(vals), 2),
                "stdev":  round(statistics.stdev(vals), 2) if len(vals) > 1 else 0,
                "min":    min(vals),
                "max":    max(vals),
            }
        return self._pass("Distribution computed", distribution=stats)


class NegativeValueCheck(DataCheck):
    """Flag negative values in columns that must be non-negative."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    def run(self, data: list[dict], columns: list[str] | None = None, **_) -> CheckResult:
        if not columns:
            return self._pass("No columns specified — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col in columns:
                val = row.get(col)
                try:
                    if val is not None and float(val) < 0:
                        violations.setdefault(col, []).append(
                            {"row": idx, "value": val})
                except (TypeError, ValueError):
                    pass
        if violations:
            return self._fail(f"Negative values in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("No negative values found")


class PercentageTotalCheck(DataCheck):
    """Validate percentage columns sum to 100 (within tolerance)."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    def run(self, data: list[dict], percentage_column: str | None = None,
            expected_total: float = 100.0, tolerance: float = 0.01, **_) -> CheckResult:
        if not percentage_column:
            return self._pass("No percentage column specified — skipped")
        total = sum(float(r[percentage_column])
                    for r in data if r.get(percentage_column) is not None)
        diff = abs(total - expected_total)
        if diff > tolerance:
            return self._fail(f"Percentages sum to {total:.2f}, expected {expected_total}",
                              total=total, expected=expected_total, diff=round(diff, 4))
        return self._pass(f"Percentages sum to {total:.2f}")


class StringLengthCheck(DataCheck):
    """Validate string lengths within [min, max] bounds."""
    tier = CheckTier.ADVANCED
    severity = Severity.WARNING

    def run(self, data: list[dict],
            length_rules: dict[str, list[int]] | None = None, **_) -> CheckResult:
        if not length_rules:
            return self._pass("No length rules provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col, bounds in length_rules.items():
                lo, hi = bounds[0], bounds[1]
                val = row.get(col)
                if val is None:
                    continue
                length = len(str(val))
                if not (lo <= length <= hi):
                    violations.setdefault(col, []).append({
                        "row": idx, "value": str(val)[:30], "length": length
                    })
        if violations:
            return self._fail(f"String length violations in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("All string lengths within bounds")


class CompletenessCheck(DataCheck):
    """Ensure expected partition keys / dates are all present."""
    tier = CheckTier.ADVANCED
    severity = Severity.CRITICAL

    def run(self, data: list[dict], partition_column: str | None = None,
            expected_partitions: list | None = None, **_) -> CheckResult:
        if not partition_column or expected_partitions is None:
            return self._pass("No partition config provided — skipped")
        found = {row.get(partition_column) for row in data}
        missing = set(expected_partitions) - found
        if missing:
            return self._fail(f"{len(missing)} partition(s) missing",
                              missing=sorted(str(p) for p in missing))
        return self._pass("All expected partitions are present")
