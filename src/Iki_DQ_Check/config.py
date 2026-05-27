from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass
class DQConfig:

    # Lite
    pk_column: str = "id"
    columns: list[str] | None = None
    schema: dict[str, str] | None = None
    ranges: dict[str, tuple[float | None, float | None]] | None = None
    key_columns: list[str] | None = None

    # Standard
    patterns: dict[str, str] | None = None
    allowed: dict[str, list[Any]] | None = None
    rules: dict[str, Callable[[dict], bool]] | None = None
    cross_rules: dict[str, Callable[[dict], bool]] | None = None
    latest_timestamp: datetime | None = None
    max_delay_hours: float = 24.0
    expected_min: int | None = None
    expected_max: int | None = None
    fk_column: str | None = None
    reference_values: list[Any] | None = None

    # Advanced
    expected_columns: list[str] | None = None
    file_name_column: str = "file_name"
    parent_column: str | None = None
    child_column: str | None = None
    valid_hierarchy: dict[str, list[Any]] | None = None
    audit_columns: list[str] | None = None
    source_count: int | None = None
    target_count: int | None = None
    tolerance_pct: float = 0.01
    source_payload: str | None = None
    target_payload: str | None = None
    code_column: str | None = None
    valid_codes: list[Any] | None = None
    percentage_column: str | None = None
    expected_total: float = 100.0
    length_rules: dict[str, tuple[int, int]] | None = None
    partition_column: str | None = None
    expected_partitions: list[Any] | None = None

    def to_kwargs(self) -> dict[str, Any]:
        always_include = {
            "pk_column", "max_delay_hours", "tolerance_pct",
            "expected_total", "file_name_column",
        }
        return {
            f: getattr(self, f)
            for f in self.__dataclass_fields__
            if getattr(self, f) is not None or f in always_include
        }

    def with_rules_from_expr(self, **exprs: str) -> "DQConfig":
        from .cli.loaders import safe_eval_rule
        compiled = {name: safe_eval_rule(expr)
                    for name, expr in exprs.items()}
        self.rules = {**(self.rules or {}), **compiled}
        return self

    def with_cross_rules_from_expr(self, **exprs: str) -> "DQConfig":
        from .cli.loaders import safe_eval_rule
        compiled = {name: safe_eval_rule(expr)
                    for name, expr in exprs.items()}
        self.cross_rules = {**(self.cross_rules or {}), **compiled}
        return self


def lite_config(pk_column: str = "id", **kwargs) -> DQConfig:
    return DQConfig(pk_column=pk_column, **kwargs)


def standard_config(
    pk_column: str = "id",
    *,
    patterns: dict | None = None,
    allowed: dict | None = None,
    rules: dict | None = None,
    **kwargs,
) -> DQConfig:
    return DQConfig(pk_column=pk_column, patterns=patterns,
                    allowed=allowed, rules=rules, **kwargs)


def advanced_config(pk_column: str = "id", **kwargs) -> DQConfig:
    return DQConfig(pk_column=pk_column, **kwargs)
