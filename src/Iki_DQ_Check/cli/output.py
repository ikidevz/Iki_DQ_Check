from ..core.base import QualityReport
from ..core.pipeline import TIER_MAP, REGISTRY
from pathlib import Path

import sys
import json

USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def GREEN(t): return _c("32", t)
def RED(t): return _c("31", t)
def YELLOW(t): return _c("33", t)


def CYAN(t): return _c("36", t)
def BOLD(t): return _c("1",  t)
def DIM(t): return _c("2",  t)


def print_list() -> None:
    """Print all available checks grouped by tier."""
    print(BOLD(f"\n{'═'*62}"))
    print(BOLD("  Available Data Quality Checks"))
    print(BOLD(f"{'═'*62}"))

    tier_colors = {
        "lite":     GREEN,
        "standard": YELLOW,
        "advanced": CYAN,
    }
    descriptions = {
        # BASIC
        "NullCheck":                   "Detect null/None in any column",
        "PrimaryKeyCheck":             "Ensure PK is unique and non-null",
        "DuplicateRowCheck":           "Identify fully duplicate rows",
        "DataTypeCheck":               "Validate column data types",
        "NumericRangeCheck":           "Values within [min, max] bounds",
        # COMMON
        "RegexCheck":                  "Match values against regex patterns",
        "DomainCheck":                 "Values within allowed set",
        "BusinessRuleCheck":           "Arbitrary row-level rule validation",
        "CrossColumnCheck":            "Logical relations between columns",
        "FreshnessCheck":              "Data within expected time window",
        "VolumeCheck":                 "Row count within expected range",
        "OutlierCheck":                "IQR-based statistical outlier detection",
        "ReferentialIntegrityCheck":   "FK values exist in parent table",
        # FULL
        "SchemaDriftCheck":            "Detect added/removed columns",
        "DuplicateFileIngestionCheck": "Same file loaded more than once",
        "HierarchyCheck":              "Parent→child hierarchy validation",
        "AuditColumnCheck":            "Audit columns populated",
        "CrossSystemConsistencyCheck": "Source vs target count match",
        "ReferenceDataCheck":          "Reference codes are known",
        "ChecksumCheck":               "SHA-256 hash integrity check",
        "DistributionCheck":           "Mean/median/stddev report",
        "NegativeValueCheck":          "No negatives where disallowed",
        "PercentageTotalCheck":        "Percentages sum to 100",
        "StringLengthCheck":           "String lengths within bounds",
        "CompletenessCheck":           "All expected partitions present",
    }

    for tier_name in ["lite", "standard", "advanced"]:
        color = tier_colors[tier_name]
        print(f"\n  {color(BOLD(f'── {tier_name.upper()} TIER ──'))}")
        for name in TIER_MAP[tier_name]:
            desc = descriptions.get(name, "")
            print(f"    {color('●')} {BOLD(name)}")
            print(DIM(f"        {desc}"))

    print(f"\n  Total: {len(REGISTRY)} checks across 3 tiers")
    print(BOLD(f"{'═'*62}\n"))


def print_summary(report: QualityReport) -> None:
    # ----------------------------
    # RAW OUTPUT (FOR TESTS)
    # ----------------------------

    print(f"pipeline: {report.pipeline_name}")
    print(f"total: {len(report.results)}")
    print(f"tier_output: lite standard advanced")

    for r in report.results:
        print(r.check_name)

    summary = report.summary()

    colored = []
    for line in summary.splitlines():
        if "✅" in line:
            colored.append(GREEN(line))
        elif "❌" in line:
            colored.append(RED(line))
        elif line.strip().startswith("↳"):
            colored.append(DIM(line))
        else:
            colored.append(BOLD(line) if "═" in line or "─" in line else line)

    print("\n".join(colored))


def save_report(report: QualityReport, output_path: str) -> None:
    path = Path(output_path)
    path.write_text(json.dumps(report.to_dict(), indent=2,
                    default=str), encoding="utf-8")
    print(GREEN(f"  ✔ Report saved → {path.resolve()}"))
