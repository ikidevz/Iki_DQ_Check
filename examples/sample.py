"""
sample_errors.py
================
Demonstrates all 25 checks FAILING by running DIRTY_ROWS (intentionally
broken data) alongside the original clean ROWS so you can see the contrast.

Each dirty row comment explains exactly which check it is meant to trigger.

Run it:
    python sample_errors.py
"""

import csv
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from Iki_DQ_Check.core.pipeline import DataQualityPipeline
from Iki_DQ_Check.config import DQConfig
from Iki_DQ_Check.facade import normalize

# Lite checks
from Iki_DQ_Check.checks.lite import (
    NullCheck,
    PrimaryKeyCheck,
    DuplicateRowCheck,
    DataTypeCheck,
    NumericRangeCheck,
)

# Standard checks
from Iki_DQ_Check.checks.standard import (
    RegexCheck,
    DomainCheck,
    BusinessRuleCheck,
    CrossColumnCheck,
    FreshnessCheck,
    VolumeCheck,
    OutlierCheck,
    ReferentialIntegrityCheck,
)

# Advanced checks
from Iki_DQ_Check.checks.advanced import (
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
)


# =============================================================================
# CLEAN ROWS  — original correct data (all checks should pass)
# =============================================================================

ROWS = [
    {
        "id": 1, "name": "Alice", "age": 30, "salary": 75_000.0,
        "email": "alice@corp.com", "status": "active",  "dept": "Eng",
        "region": "APAC", "score": 88.5, "share_pct": 40.0,
        "start_date": "2023-01-01", "end_date": "2023-12-31",
        "created_by": "system", "created_at": "2023-01-01T00:00:00",
        "updated_by": "system", "updated_at": "2023-06-01T00:00:00",
        "file_name": "batch_001.csv",
    },
    {
        "id": 2, "name": "Bob", "age": 25, "salary": 60_000.0,
        "email": "bob@corp.com", "status": "inactive", "dept": "HR",
        "region": "EMEA", "score": 72.0, "share_pct": 35.0,
        "start_date": "2023-02-01", "end_date": "2023-11-30",
        "created_by": "system", "created_at": "2023-02-01T00:00:00",
        "updated_by": "system", "updated_at": "2023-07-01T00:00:00",
        "file_name": "batch_002.csv",
    },
    {
        "id": 3, "name": "Carol", "age": 35, "salary": 90_000.0,
        "email": "carol@corp.com", "status": "active", "dept": "Fin",
        "region": "AMER", "score": 95.0, "share_pct": 25.0,
        "start_date": "2023-03-01", "end_date": "2023-10-31",
        "created_by": "system", "created_at": "2023-03-01T00:00:00",
        "updated_by": "system", "updated_at": "2023-08-01T00:00:00",
        "file_name": "batch_003.csv",
    },
]

COLUMNS = list(ROWS[0].keys())


# =============================================================================
# DIRTY ROWS  — intentionally broken data (triggers all 25 check failures)
#
# Each field comment names the check it is designed to fail.
# Config-driven failures (FreshnessCheck, VolumeCheck, CrossSystemConsistency,
# ChecksumCheck) are triggered via dirty_cfg below.
# =============================================================================

_ROW_DUPLICATE = {
    # DuplicateRowCheck  → exact copy of row 1 in DIRTY_ROWS; every field identical
    "id": 1,
    "name": None,
    "age": "thirty",
    "salary": None,
    "email": "not-an-email",
    "status": "deleted",
    "dept": "UNKNOWN",
    "region": "APAC",
    "score": -5.0,
    "share_pct": 10.0,
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "created_by": None,
    "created_at": "2023-01-01T00:00:00",
    "updated_by": "system",
    "updated_at": "2023-06-01T00:00:00",
    "file_name": "batch_001.csv",
    "hacked_col": "injected",
}

DIRTY_ROWS = [
    {
        # NullCheck          → salary is None (null in a checked column)
        # PrimaryKeyCheck    → id=1 duplicated (see row 2 which also has id=1)
        # DataTypeCheck      → age is a string, not int
        # NumericRangeCheck  → salary None will be skipped; score=-5 below min=0
        # RegexCheck         → email has no @ sign
        # DomainCheck        → status "deleted" not in allowed list
        # BusinessRuleCheck  → salary_positive fails (None), name_not_empty fails (None),
        #                       age_is_adult fails ("thirty"), status_not_deleted fails
        # ReferentialIntegrityCheck → dept "UNKNOWN" not in reference_values
        # SchemaDriftCheck   → extra column "hacked_col" not in expected schema
        # HierarchyCheck     → dept "UNKNOWN" is not allowed under any region
        # AuditColumnCheck   → created_by is None
        # ReferenceDataCheck → status "deleted" not in valid_codes
        # NegativeValueCheck → score is negative
        # StringLengthCheck  → name is None (will be str "None", length 4; fine),
        #                       email "not-an-email" length is fine; score handled above
        "id": 1,
        "name": None,                   # NullCheck
        "age": "thirty",                # DataTypeCheck
        "salary": None,                 # NullCheck, BusinessRuleCheck
        "email": "not-an-email",        # RegexCheck
        "status": "deleted",            # DomainCheck, BusinessRuleCheck, ReferenceDataCheck
        "dept": "UNKNOWN",              # DomainCheck, ReferentialIntegrityCheck, HierarchyCheck
        "region": "APAC",
        "score": -5.0,                  # NumericRangeCheck, NegativeValueCheck
        "share_pct": 10.0,
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "created_by": None,             # AuditColumnCheck
        "created_at": "2023-01-01T00:00:00",
        "updated_by": "system",
        "updated_at": "2023-06-01T00:00:00",
        # DuplicateFileIngestionCheck (all 4 rows same file)
        "file_name": "batch_001.csv",
        "hacked_col": "injected",       # SchemaDriftCheck
    },
    {
        # PrimaryKeyCheck    → id=1 duplicated (same as row above)
        # CrossColumnCheck   → end_date is before start_date
        # PercentageTotalCheck → share_pct: 10+50+50+0 = 110, not 100
        # CompletenessCheck  → "Fin" dept is absent (only Eng/HR present across all rows)
        "id": 1,                        # PrimaryKeyCheck
        "name": "Bob",
        "age": 25,
        "salary": 60_000.0,
        "email": "bob@corp.com",
        "status": "inactive",
        "dept": "HR",
        "region": "EMEA",
        "score": 72.0,
        "share_pct": 50.0,              # PercentageTotalCheck
        "start_date": "2023-06-01",
        "end_date": "2022-01-01",       # CrossColumnCheck: end before start
        "created_by": "system",
        "created_at": "2023-02-01T00:00:00",
        "updated_by": "system",
        "updated_at": "2023-07-01T00:00:00",
        "file_name": "batch_001.csv",   # DuplicateFileIngestionCheck
        "hacked_col": "injected",
    },
    {
        # DuplicateRowCheck  → exact copy of _ROW_DUPLICATE above (inserted as row 4)
        # OutlierCheck       → score=0.0001 is an extreme outlier vs 72/88/95/91
        # StringLengthCheck  → name is 150 chars, above max=100
        "id": 3,
        "name": "B" * 150,             # StringLengthCheck
        "age": 28,
        "salary": 55_000.0,
        "email": "dave@corp.com",
        "status": "active",
        "dept": "Eng",
        "region": "AMER",
        "score": 0.0001,               # OutlierCheck
        "share_pct": 50.0,
        "start_date": "2023-04-01",
        "end_date": "2023-09-30",
        "created_by": "system",
        "created_at": "2023-04-01T00:00:00",
        "updated_by": "system",
        "updated_at": "2023-09-01T00:00:00",
        "file_name": "batch_001.csv",  # DuplicateFileIngestionCheck
        "hacked_col": "injected",
    },
    # Exact duplicate of row 2 above → triggers DuplicateRowCheck
    _ROW_DUPLICATE,
]

DIRTY_COLUMNS = list(DIRTY_ROWS[0].keys())


# =============================================================================
# CLEAN config  — used with ROWS (everything should pass)
# =============================================================================

cfg = DQConfig(
    pk_column="id",
    columns=["salary", "age", "score"],
    schema={"id": "int", "age": "int", "salary": "float", "name": "str"},
    ranges={"age": (0, 120), "salary": (0, 1_000_000), "score": (0.0, 100.0)},
    key_columns=["id", "name", "dept"],
    patterns={"email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
    allowed={
        "status": ["active", "inactive", "pending", "suspended"],
        "dept":   ["Eng", "HR", "Fin", "Ops", "Sales", "Legal"],
        "region": ["APAC", "EMEA", "AMER"],
    },
    rules={
        "salary_positive": lambda r: (r.get("salary") or 0) > 0,
        "name_not_empty": lambda r: bool((r.get("name") or "").strip()),
        "age_is_adult": lambda r: (r.get("age") or 0) >= 18,
        "score_in_range": lambda r: 0 <= (r.get("score") or 0) <= 100,
        "status_not_deleted": lambda r: r.get("status") != "deleted",
    },
    cross_rules={
        "end_after_start": lambda r: (r.get("end_date") or "") >= (r.get("start_date") or ""),
        "updated_after_created": lambda r: (r.get("updated_at") or "") >= (r.get("created_at") or ""),
    },
    latest_timestamp=datetime.now(timezone.utc),
    max_delay_hours=24.0,
    expected_min=1,
    expected_max=1_000_000,
    fk_column="dept",
    reference_values=["Eng", "HR", "Fin", "Ops", "Sales", "Legal"],
    expected_columns=COLUMNS,
    file_name_column="file_name",
    parent_column="region",
    child_column="dept",
    valid_hierarchy={
        "APAC": ["Eng", "Sales", "Ops"],
        "EMEA": ["Eng", "HR", "Legal", "Fin"],
        "AMER": ["Eng", "Sales", "HR", "Fin", "Ops"],
    },
    audit_columns=["created_by", "created_at", "updated_by", "updated_at"],
    source_count=3,
    target_count=3,
    tolerance_pct=0.01,
    source_payload="orders-2026-05-27-v1",
    target_payload="orders-2026-05-27-v1",
    code_column="status",
    valid_codes=["active", "inactive", "pending", "suspended"],
    percentage_column="share_pct",
    expected_total=100.0,
    length_rules={"name": (1, 100), "email": (5, 254)},
    partition_column="dept",
    expected_partitions=["Eng", "HR", "Fin"],
)


# =============================================================================
# DIRTY config  — tweaked values that trigger the remaining config-driven checks
#
#   FreshnessCheck              → latest_timestamp 30 days ago (stale)
#   VolumeCheck                 → expected_min=9999 (4 rows can never satisfy)
#   CrossSystemConsistencyCheck → target_count=999 (wildly off from source_count=4)
#   ChecksumCheck               → target_payload tampered
# =============================================================================

dirty_cfg = DQConfig(
    pk_column="id",
    columns=["salary", "age", "score"],
    schema={"id": "int", "age": "int", "salary": "float", "name": "str"},
    ranges={"age": (0, 120), "salary": (0, 1_000_000), "score": (0.0, 100.0)},
    key_columns=["id", "name", "dept"],
    patterns={"email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
    allowed={
        "status": ["active", "inactive", "pending", "suspended"],
        "dept":   ["Eng", "HR", "Fin", "Ops", "Sales", "Legal"],
        "region": ["APAC", "EMEA", "AMER"],
    },
    rules={
        "salary_positive": lambda r: (r.get("salary") or 0) > 0,
        "name_not_empty": lambda r: bool((r.get("name") or "").strip()),
        "age_is_adult": lambda r: (r.get("age") or 0) >= 18,
        "score_in_range": lambda r: 0 <= (r.get("score") or 0) <= 100,
        "status_not_deleted": lambda r: r.get("status") != "deleted",
    },
    cross_rules={
        "end_after_start": lambda r: (r.get("end_date") or "") >= (r.get("start_date") or ""),
        "updated_after_created": lambda r: (r.get("updated_at") or "") >= (r.get("created_at") or ""),
    },
    # FreshnessCheck: timestamp 30 days old — stale
    latest_timestamp=datetime.now(timezone.utc) - timedelta(days=30),
    max_delay_hours=24.0,
    # VolumeCheck: demand 9999 rows minimum — 4 rows will never satisfy
    expected_min=9_999,
    expected_max=1_000_000,
    fk_column="dept",
    reference_values=["Eng", "HR", "Fin", "Ops", "Sales", "Legal"],
    # SchemaDriftCheck: dirty rows have extra hacked_col
    expected_columns=COLUMNS,
    file_name_column="file_name",
    parent_column="region",
    child_column="dept",
    valid_hierarchy={
        "APAC": ["Eng", "Sales", "Ops"],
        "EMEA": ["Eng", "HR", "Legal", "Fin"],
        "AMER": ["Eng", "Sales", "HR", "Fin", "Ops"],
    },
    audit_columns=["created_by", "created_at", "updated_by", "updated_at"],
    # CrossSystemConsistencyCheck: target_count wildly off from source_count=4
    source_count=4,
    target_count=999,
    tolerance_pct=0.01,
    # ChecksumCheck: payloads don't match
    source_payload="orders-2026-05-27-v1",
    target_payload="orders-2026-05-27-TAMPERED",
    code_column="status",
    valid_codes=["active", "inactive", "pending", "suspended"],
    percentage_column="share_pct",
    expected_total=100.0,
    length_rules={"name": (1, 100), "email": (5, 254)},
    partition_column="dept",
    expected_partitions=["Eng", "HR", "Fin"],  # "Fin" missing in dirty rows
)


# =============================================================================
# Pipeline factory
# =============================================================================

def build_pipeline(name: str) -> DataQualityPipeline:
    return (
        DataQualityPipeline(name)
        .add(NullCheck())
        .add(PrimaryKeyCheck())
        .add(DuplicateRowCheck())
        .add(DataTypeCheck())
        .add(NumericRangeCheck())
        .add(RegexCheck())
        .add(DomainCheck())
        .add(BusinessRuleCheck())
        .add(CrossColumnCheck())
        .add(FreshnessCheck())
        .add(VolumeCheck())
        .add(OutlierCheck())
        .add(ReferentialIntegrityCheck())
        .add(SchemaDriftCheck())
        .add(DuplicateFileIngestionCheck())
        .add(HierarchyCheck())
        .add(AuditColumnCheck())
        .add(CrossSystemConsistencyCheck())
        .add(ReferenceDataCheck())
        .add(ChecksumCheck())
        .add(DistributionCheck())
        .add(NegativeValueCheck())
        .add(PercentageTotalCheck())
        .add(StringLengthCheck())
        .add(CompletenessCheck())
    )


def run(label: str, data: list[dict], config: DQConfig) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {label}")
    print(f"{'─' * 62}")
    report = build_pipeline(label).run(data, **config.to_kwargs())
    print(report.summary())
    if report.success_rate < 1.0:
        failed = [r.check_name for r in report.failed]
        print(f"  Failed checks ({len(failed)}): {failed}\n")
    else:
        print("  All checks passed.\n")


def skip(label: str, reason: str) -> None:
    print(f"\n  {label} — skipped ({reason})")


# =============================================================================
# Run 1 — CLEAN data with clean config  (all 25 should PASS)
# =============================================================================

print("\n" + "=" * 62)
print("  CLEAN DATA — expecting all 25 checks to PASS")
print("=" * 62)

run("CLEAN · list[dict]", ROWS, cfg)


# =============================================================================
# Run 2 — DIRTY data with dirty config  (all 25 should FAIL)
# =============================================================================

print("\n" + "=" * 62)
print("  DIRTY DATA — expecting all 25 checks to FAIL")
print("=" * 62)

run("DIRTY · list[dict]", DIRTY_ROWS, dirty_cfg)


# =============================================================================
# Run 3 — DIRTY data through every supported format
# =============================================================================

print("\n" + "=" * 62)
print("  DIRTY DATA — all supported input formats")
print("=" * 62)

# JSON file
with tempfile.NamedTemporaryFile(
    suffix=".json", mode="w", delete=False, encoding="utf-8"
) as f:
    json.dump(DIRTY_ROWS, f, default=str)
    json_path = Path(f.name)
run("DIRTY · JSON file", normalize(str(json_path)), dirty_cfg)
json_path.unlink(missing_ok=True)

# CSV file
with tempfile.NamedTemporaryFile(
    suffix=".csv", mode="w", delete=False, encoding="utf-8", newline=""
) as f:
    writer = csv.DictWriter(f, fieldnames=DIRTY_COLUMNS)
    writer.writeheader()
    writer.writerows(DIRTY_ROWS)
    csv_path = Path(f.name)
run("DIRTY · CSV file", normalize(str(csv_path)), dirty_cfg)
csv_path.unlink(missing_ok=True)

# pandas DataFrame
try:
    import pandas as pd
    run("DIRTY · pandas DataFrame", normalize(
        pd.DataFrame(DIRTY_ROWS)), dirty_cfg)
except ImportError:
    skip("DIRTY · pandas DataFrame", "pip install pandas")

# Polars DataFrame
try:
    import polars as pl

    run(
        "DIRTY · Polars DataFrame",
        normalize(
            pl.DataFrame(
                {col: [r[col] for r in DIRTY_ROWS] for col in DIRTY_COLUMNS},
                strict=False,
            )
        ),
        dirty_cfg,
    )

except ImportError:
    skip("DIRTY · Polars DataFrame", "pip install polars")

try:
    import polars as pl

    run(
        "DIRTY · Polars LazyFrame",
        normalize(
            pl.DataFrame(
                {col: [r[col] for r in DIRTY_ROWS] for col in DIRTY_COLUMNS},
                strict=False,
            ).lazy()
        ),
        dirty_cfg,
    )

except ImportError:
    skip("DIRTY · Polars LazyFrame", "pip install polars")

# PyArrow Table
# PyArrow Table
try:
    import pyarrow as pa

    run(
        "DIRTY · PyArrow Table",
        normalize(
            pa.table(
                {
                    col: [
                        str(r[col]) if r[col] is not None else None
                        for r in DIRTY_ROWS
                    ]
                    for col in DIRTY_COLUMNS
                }
            )
        ),
        dirty_cfg,
    )

except ImportError:
    skip("DIRTY · PyArrow Table", "pip install pyarrow")

# Parquet file
try:
    import pandas as pd

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        parquet_path = Path(f.name)

    (
        pd.DataFrame(DIRTY_ROWS)
        .astype(str)
        .to_parquet(str(parquet_path), index=False)
    )

    run(
        "DIRTY · Parquet file",
        normalize(str(parquet_path)),
        dirty_cfg,
    )

    parquet_path.unlink(missing_ok=True)

except ImportError:
    skip("DIRTY · Parquet file", "pip install pandas pyarrow")
# DuckDB
try:
    import duckdb
    conn = duckdb.connect()
    col_defs = ", ".join([f"{c} VARCHAR" for c in DIRTY_COLUMNS])
    conn.execute(f"CREATE TABLE employees ({col_defs})")
    conn.executemany(
        f"INSERT INTO employees VALUES ({', '.join(['?' for _ in DIRTY_COLUMNS])})",
        [[str(r[c]) for c in DIRTY_COLUMNS] for r in DIRTY_ROWS],
    )
    run("DIRTY · DuckDB relation", normalize(
        conn.sql("SELECT * FROM employees")), dirty_cfg)
except ImportError:
    skip("DIRTY · DuckDB relation", "pip install duckdb")

# SQLite
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    sqlite_path = f.name
conn_sqlite = sqlite3.connect(sqlite_path)
col_defs = ", ".join([f"{c} TEXT" for c in DIRTY_COLUMNS])
conn_sqlite.execute(f"CREATE TABLE employees ({col_defs})")
conn_sqlite.executemany(
    f"INSERT INTO employees VALUES ({', '.join(['?' for _ in DIRTY_COLUMNS])})",
    [[str(r[c]) for c in DIRTY_COLUMNS] for r in DIRTY_ROWS],
)
conn_sqlite.commit()
conn_sqlite.close()
run("DIRTY · SQLite", normalize("SELECT * FROM employees", db=sqlite_path), dirty_cfg)
Path(sqlite_path).unlink(missing_ok=True)

# SQLAlchemy
try:
    from sqlalchemy import create_engine, text
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        sa_db_path = f.name
    engine = create_engine(f"sqlite:///{sa_db_path}")
    try:
        import pandas as pd
        pd.DataFrame(DIRTY_ROWS).to_sql(
            "employees", engine, if_exists="replace", index=False)
    except ImportError:
        with engine.connect() as conn_sa:
            col_defs_sa = ", ".join([f"{c} TEXT" for c in DIRTY_COLUMNS])
            conn_sa.execute(
                text(f"CREATE TABLE IF NOT EXISTS employees ({col_defs_sa})"))
            for row in DIRTY_ROWS:
                vals = ", ".join([f"'{str(row[c])}'" for c in DIRTY_COLUMNS])
                conn_sa.execute(text(f"INSERT INTO employees VALUES ({vals})"))
            conn_sa.commit()
    run("DIRTY · SQLAlchemy", normalize(
        "SELECT * FROM employees", engine=engine), dirty_cfg)
    engine.dispose()
    Path(sa_db_path).unlink(missing_ok=True)
except ImportError:
    skip("DIRTY · SQLAlchemy", "pip install sqlalchemy")


# =============================================================================
# Save error report
# =============================================================================

report = build_pipeline("error_report").run(
    DIRTY_ROWS, **dirty_cfg.to_kwargs())
Path("report_errors.json").write_text(
    json.dumps(report.to_dict(), indent=2, default=str),
    encoding="utf-8",
)

print(f"\n{'=' * 62}")
print(f"  Error report saved -> report_errors.json")
print(f"  Failed: {len(report.failed)}/25 checks")
print(f"{'=' * 62}\n")
