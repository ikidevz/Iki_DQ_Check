from ..core import DataCheck, CheckTier, CheckResult
from collections import Counter
from typing import Callable


class NullCheck(DataCheck):
    """Detect null / None values in specified (or all) columns."""
    tier = CheckTier.LITE

    def run(self, data: list[dict], columns: list[str] | None = None, **_) -> CheckResult:
        nulls: dict[str, list[int]] = {}
        cols = columns or (list(data[0].keys()) if data else [])
        for idx, row in enumerate(data):
            for col in cols:
                if row.get(col) is None:
                    nulls.setdefault(col, []).append(idx)
        if nulls:
            return self._fail(f"Nulls in {len(nulls)} column(s)", null_columns=nulls,
                              total=sum(len(v) for v in nulls.values()))
        return self._pass("No null values found")


class PrimaryKeyCheck(DataCheck):
    """Ensure PK column is unique and non-null."""
    tier = CheckTier.LITE

    def run(self, data: list[dict], pk_column: str = "id", **_) -> CheckResult:
        seen: set = set()
        dupes: list = []
        nulls = 0
        for row in data:
            val = row.get(pk_column)
            if val is None:
                nulls += 1
            elif val in seen:
                dupes.append(val)
            else:
                seen.add(val)
        if nulls or dupes:
            return self._fail(f"PK '{pk_column}' violations found",
                              null_pks=nulls, duplicate_values=dupes)
        return self._pass(f"PK '{pk_column}' is valid")


class DuplicateRowCheck(DataCheck):
    """Detect fully duplicate rows."""
    tier = CheckTier.LITE

    def run(self, data: list[dict], key_columns: list[str] | None = None, **_) -> CheckResult:
        def row_key(row: dict) -> tuple:
            cols = key_columns or sorted(row.keys())
            return tuple(row.get(c) for c in cols)
        counts = Counter(row_key(r) for r in data)
        dupes = {str(k): v for k, v in counts.items() if v > 1}
        if dupes:
            return self._fail(f"{len(dupes)} duplicate row group(s)",
                              duplicated_keys=list(dupes.keys())[:10])
        return self._pass("No duplicate rows found")


class DataTypeCheck(DataCheck):
    """Validate values can be cast to expected Python types."""
    tier = CheckTier.LITE

    TYPE_MAP: dict[str, Callable] = {
        "int": int, "float": float, "str": str, "bool": bool}

    def run(self, data: list[dict], schema: dict[str, str] | None = None, **_) -> CheckResult:
        if not schema:
            return self._pass("No schema provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col, type_name in schema.items():
                val = row.get(col)
                if val is None:
                    continue
                caster = self.TYPE_MAP.get(type_name, str)
                try:
                    caster(val)
                except (ValueError, TypeError):
                    violations.setdefault(col, []).append(
                        {"row": idx, "value": val})
        if violations:
            return self._fail(f"Type violations in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("All columns pass type check")


class NumericRangeCheck(DataCheck):
    """Validate numeric values within [min, max]."""
    tier = CheckTier.LITE

    def run(self, data: list[dict],
            ranges: dict[str, tuple[float | None, float | None]] | None = None, **_) -> CheckResult:
        if not ranges:
            return self._pass("No ranges provided — skipped")
        violations: dict[str, list] = {}
        for idx, row in enumerate(data):
            for col, (lo, hi) in ranges.items():
                val = row.get(col)
                if val is None:
                    continue
                try:
                    v = float(val)
                except (TypeError, ValueError):
                    continue
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    violations.setdefault(col, []).append(
                        {"row": idx, "value": val})
        if violations:
            return self._fail(f"Range violations in {len(violations)} column(s)",
                              violations=violations)
        return self._pass("All numeric ranges are valid")
