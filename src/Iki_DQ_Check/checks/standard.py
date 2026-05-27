from ..core import DataCheck, CheckTier, CheckResult, Severity
from typing import Callable, Any
from datetime import datetime, timezone
import re
import statistics


class RegexCheck(DataCheck):
    """Validate column values against regex patterns."""
    tier = CheckTier.STANDARD
    severity = Severity.WARNING

    def run(self, data: list[dict], patterns: dict[str, str] | None = None, **_) -> CheckResult:
        if not patterns:
            return self._pass("No patterns provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col, pattern in patterns.items():
                val = str(row.get(col, "") or "")
                if not re.fullmatch(pattern, val):
                    violations.setdefault(col, []).append(
                        {"row": idx, "value": val})
        if violations:
            return self._fail(f"Regex violations in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("All values match regex patterns")


class DomainCheck(DataCheck):
    """Validate values belong to an allowed set."""
    tier = CheckTier.STANDARD
    severity = Severity.WARNING

    def run(self, data: list[dict], allowed: dict[str, list] | None = None, **_) -> CheckResult:
        if not allowed:
            return self._pass("No domain rules provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col, valid_values in allowed.items():
                val = row.get(col)
                if val not in set(valid_values):
                    violations.setdefault(col, []).append(
                        {"row": idx, "value": val})
        if violations:
            return self._fail(f"Domain violations in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("All values within allowed domain")


class BusinessRuleCheck(DataCheck):
    """Validate arbitrary row-level business rules (callables)."""
    tier = CheckTier.STANDARD
    severity = Severity.CRITICAL

    def run(self, data: list[dict],
            rules: dict[str, Callable[[dict], bool]] | None = None, **_) -> CheckResult:
        if not rules:
            return self._pass("No business rules provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for rule_name, predicate in rules.items():
                try:
                    if not predicate(row):
                        violations.setdefault(rule_name, []).append(idx)
                except Exception as exc:
                    violations.setdefault(rule_name, []).append(
                        f"row {idx}: {exc}")
        if violations:
            return self._fail(f"{len(violations)} business rule(s) failed",
                              violations=violations)
        return self._pass("All business rules passed")


class CrossColumnCheck(DataCheck):
    """Validate logical relationships between columns."""
    tier = CheckTier.STANDARD
    severity = Severity.CRITICAL

    def run(self, data: list[dict],
            cross_rules: dict[str, Callable[[dict], bool]] | None = None, **_) -> CheckResult:
        if not cross_rules:
            return self._pass("No cross-column rules provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for name, pred in cross_rules.items():
                try:
                    if not pred(row):
                        violations.setdefault(name, []).append(idx)
                except Exception as exc:
                    violations.setdefault(name, []).append(str(exc))
        if violations:
            return self._fail("Cross-column consistency violated", violations=violations)
        return self._pass("Cross-column checks passed")


class FreshnessCheck(DataCheck):
    """Validate data arrived within an expected time window."""
    tier = CheckTier.STANDARD
    severity = Severity.CRITICAL

    def run(self, data: Any, latest_timestamp: datetime | None = None,
            max_delay_hours: float = 2.0, **_) -> CheckResult:
        if latest_timestamp is None:
            return self._pass("No timestamp provided — skipped")
        now = datetime.now(timezone.utc)
        ts = latest_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (now - ts).total_seconds() / 3600
        if round(age_hours, 4) > max_delay_hours:
            return self._fail(f"Data is {age_hours:.1f}h old (max: {max_delay_hours}h)",
                              delay_hours=round(age_hours, 2))
        return self._pass(f"Data is fresh ({age_hours:.1f}h old)")


class VolumeCheck(DataCheck):
    """Row count must stay within expected range."""
    tier = CheckTier.STANDARD
    severity = Severity.WARNING

    def run(self, data: list[dict], expected_min: int = 0,
            expected_max: int = 10_000_000, **_) -> CheckResult:
        count = len(data)
        if not (expected_min <= count <= expected_max):
            return self._fail(f"Row count {count} outside [{expected_min}, {expected_max}]",
                              actual=count, min=expected_min, max=expected_max)
        return self._pass(f"Row count {count} within expected range")


class OutlierCheck(DataCheck):
    """IQR-based outlier detection for numeric columns."""
    tier = CheckTier.STANDARD
    severity = Severity.WARNING

    def run(self, data: list[dict], columns: list[str] | None = None,
            iqr_multiplier: float = 1.5, **_) -> CheckResult:
        if not columns:
            return self._pass("No columns specified — skipped")
        outliers: dict[str, dict] = {}
        for col in columns:
            vals = [float(r[col]) for r in data if r.get(col) is not None]
            if len(vals) < 4:
                continue
            q1 = statistics.quantiles(sorted(vals), n=4)[0]
            q3 = statistics.quantiles(sorted(vals), n=4)[2]
            iqr = q3 - q1
            lo, hi = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
            out = [v for v in vals if v < lo or v > hi]
            if out:
                outliers[col] = {"count": len(out), "bounds": (
                    lo, hi), "examples": out[:5]}
        if outliers:
            return self._fail(f"Outliers in {len(outliers)} column(s)", outliers=outliers)
        return self._pass("No outliers detected")


class ReferentialIntegrityCheck(DataCheck):
    """FK values must exist in parent reference set."""
    tier = CheckTier.STANDARD
    severity = Severity.CRITICAL

    def run(self, data: list[dict], fk_column: str | None = None,
            reference_values: list | None = None, **_) -> CheckResult:
        if not fk_column or reference_values is None:
            return self._pass("No FK config provided — skipped")
        ref_set = set(reference_values)
        violations = [{"row": i, "value": r.get(fk_column)}
                      for i, r in enumerate(data)
                      if r.get(fk_column) is not None and r.get(fk_column) not in ref_set]
        if violations:
            return self._fail(f"{len(violations)} orphaned FK(s) in '{fk_column}'",
                              violations=violations[:10])
        return self._pass(f"All FK values in '{fk_column}' are valid")
