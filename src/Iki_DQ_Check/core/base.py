from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckTier(str, Enum):
    LITE = "LITE"
    STANDARD = "STANDARD"
    ADVANCED = "ADVANCED"


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    tier:       CheckTier
    passed:     bool
    message:    str
    severity:   Severity = Severity.CRITICAL
    details:    dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))

    def __str__(self) -> str:
        icon = "✅" if self.passed else "❌"
        prefix = f"[{self.tier.value}][{self.severity.value}]"
        return f"  {icon} {prefix} {self.check_name}: {self.message}"


@dataclass
class QualityReport:
    pipeline_name: str
    results:       list[CheckResult]
    ran_at:        datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(
        self) -> list[CheckResult]: return [r for r in self.results if r.passed]

    @property
    def failed(
        self) -> list[CheckResult]: return [r for r in self.results if not r.passed]

    @property
    def success_rate(self) -> float:
        return len(self.passed) / max(len(self.results), 1)

    def summary(self) -> str:
        w = 62
        lines = [
            f"\n{'═'*w}",
            f"  Pipeline  : {self.pipeline_name}",
            f"  Ran at    : {self.ran_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"  Total     : {len(self.results)} checks",
            f"  Passed    : {len(self.passed)} ✅",
            f"  Failed    : {len(self.failed)} ❌",
            f"  Pass rate : {self.success_rate:.0%}",
            f"{'─'*w}",
        ]
        for r in self.results:
            lines.append(str(r))
            if not r.passed and r.details:
                for k, v in list(r.details.items())[:2]:
                    lines.append(f"       ↳ {k}: {str(v)[:80]}")
        lines.append(f"{'═'*w}\n")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "pipeline_name": self.pipeline_name,
            "ran_at":        self.ran_at.isoformat(),
            "success_rate":  round(self.success_rate, 4),
            "total":         len(self.results),
            "passed":        len(self.passed),
            "failed":        len(self.failed),
            "results": [
                {
                    "check":    r.check_name,
                    "tier":     r.tier.value,
                    "passed":   r.passed,
                    "severity": r.severity.value,
                    "message":  r.message,
                    "details":  r.details,
                }
                for r in self.results
            ],
        }


class DataCheck(ABC):
    tier:     CheckTier = CheckTier.LITE
    severity: Severity = Severity.CRITICAL

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def run(self, data: Any, **kwargs: Any) -> CheckResult: ...

    def _pass(self, msg: str, **details: Any) -> CheckResult:
        return CheckResult(self.name, self.tier, True,  msg, self.severity, details)

    def _fail(self, msg: str, **details: Any) -> CheckResult:
        return CheckResult(self.name, self.tier, False, msg, self.severity, details)
