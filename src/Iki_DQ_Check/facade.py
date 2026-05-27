"""
dq_facade.py — Data Quality Facade
====================================
A single-entry-point API for the Data Quality Framework that accepts any
data format used in data engineering:

    pandas DataFrame       → pd.DataFrame
    Polars DataFrame       → pl.DataFrame / pl.LazyFrame
    Parquet file           → path string ending in .parquet
    CSV file               → path string ending in .csv
    JSON file              → path string ending in .json
    Apache Arrow Table     → pa.Table
    DuckDB relation        → duckdb.DuckDBPyRelation
    SQLAlchemy query       → str SQL + engine
    SQLite query           → str SQL + ":memory:" or db path
    Plain list of dicts    → list[dict]  (native core format)

All formats are normalized to list[dict] before being passed to the core
pipeline. No format-specific logic leaks into the checks themselves.

Jupyter-friendly: QualityReport renders as an HTML table in notebooks.

Usage:
    from dq_facade import check

    # pandas
    report = check(df, tier="lite", pk_column="id")

    # Polars
    report = check(pl_df, tier="standard", pk_column="order_id")

    # Parquet
    report = check("orders.parquet", tier="advanced", config="config.yaml")

    # SQL (DuckDB)
    import duckdb
    conn = duckdb.connect()
    report = check(conn.sql("SELECT * FROM orders"), tier="lite")

    # SQL (SQLAlchemy)
    from sqlalchemy import create_engine, text
    engine = create_engine("postgresql://...")
    report = check("SELECT * FROM orders", engine=engine, tier="lite")

    # print in terminal or render as HTML table in Jupyter
    report.show()
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any


from .core.pipeline import DataQualityPipeline, TIER_MAP, REGISTRY
from .core.base import QualityReport

# ---------------------------------------------------------------------------
# Lazy imports — none of these are required; missing ones raise clear errors
# ---------------------------------------------------------------------------


def _try_import(name: str):
    try:
        import importlib
        return importlib.import_module(name)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Core framework imports — adjust path if running outside project root
# ---------------------------------------------------------------------------

_here = Path(__file__).parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))


# ===========================================================================
# Normalizers  —  each converts one format to list[dict]
# ===========================================================================

def _from_pandas(df) -> list[dict]:
    """pandas.DataFrame → list[dict]."""
    return df.where(df.notna(), other=None).to_dict(orient="records")


def _from_polars(df) -> list[dict]:
    """polars.DataFrame or polars.LazyFrame → list[dict]."""
    pl = _try_import("polars")
    if pl and isinstance(df, pl.LazyFrame):
        df = df.collect()
    return df.to_pandas().where(
        df.to_pandas().notna(), other=None
    ).to_dict(orient="records")


def _from_arrow(table) -> list[dict]:
    """pyarrow.Table → list[dict]."""
    return table.to_pydict()  # {col: [values]} → need to zip
    # to_pydict returns col→list, not list of rows — fix below


def _from_arrow_table(table) -> list[dict]:
    """pyarrow.Table → list[dict] (row-oriented)."""
    d = table.to_pydict()
    cols = list(d.keys())
    return [
        {c: d[c][i] for c in cols}
        for i in range(table.num_rows)
    ]


def _from_parquet(path: str) -> list[dict]:
    """Parquet file path → list[dict]. Uses pyarrow, falls back to pandas."""
    pa = _try_import("pyarrow.parquet")
    if pa:
        import pyarrow.parquet as pq
        table = pq.read_table(path)
        return _from_arrow_table(table)
    pd = _try_import("pandas")
    if pd:
        import pandas as pd_mod
        return _from_pandas(pd_mod.read_parquet(path))
    raise ImportError(
        "Reading Parquet requires pyarrow or pandas.\n"
        "  pip install pyarrow    or    pip install pandas pyarrow"
    )


def _from_csv_file(path: str) -> list[dict]:
    """CSV file path → list[dict] with auto-coerced numeric values."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({k: coerce(v) for k, v in row.items()})
    return rows


def _from_json_file(path: str) -> list[dict]:
    """JSON file path → list[dict]."""
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, list):
        return raw
    for key in ("data", "records", "rows", "results"):
        if key in raw and isinstance(raw[key], list):
            return raw[key]
    raise ValueError(
        f"JSON file must contain a top-level list or a dict with a "
        f"'data'/'records'/'rows'/'results' key. Got keys: {list(raw.keys())}"
    )


def _from_duckdb(rel):
    arrow = rel.arrow()

    if hasattr(arrow, "read_all"):
        arrow = arrow.read_all()

    return _from_arrow_table(arrow)


def _from_sqlalchemy(sql: str, engine) -> list[dict]:
    """SQLAlchemy engine + SQL string → list[dict]."""
    sa = _try_import("sqlalchemy")
    if not sa:
        raise ImportError("SQLAlchemy is required.  pip install sqlalchemy")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


def _from_sqlite(sql: str, db_path: str) -> list[dict]:
    """sqlite3 db path + SQL string → list[dict]."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def coerce(v: str) -> Any:
    """Best-effort string → int / float / None coercion (CSV helper)."""
    if v in ("", "null", "NULL", "None", "NA", "N/A", "nan"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


# ===========================================================================
# Format detector  —  returns list[dict] regardless of input
# ===========================================================================

def normalize(
    data: Any,
    *,
    sql: str | None = None,
    engine=None,
    db: str | None = None,
) -> list[dict]:
    """
    Normalize any supported data format to list[dict].

    Parameters
    ----------
    data : any supported type
        DataFrame, file path string, DuckDB relation, Arrow table,
        list of dicts, or SQL string (when engine= or db= is supplied).
    sql : str, optional
        Raw SQL query string. Requires either `engine` (SQLAlchemy) or
        `db` (SQLite path / ":memory:").
    engine : sqlalchemy.Engine, optional
        SQLAlchemy engine. Used when `sql` is provided.
    db : str, optional
        SQLite database path or ":memory:". Used when `sql` is provided.
    """
    # --- plain list of dicts (native format) ---
    if isinstance(data, list):
        return data

    # --- SQL string + engine / db ---
    if isinstance(data, str) and (engine is not None or db is not None):
        if engine is not None:
            return _from_sqlalchemy(data, engine)
        if db is not None:
            return _from_sqlite(data, db)

    # --- file path strings ---
    if isinstance(data, (str, Path)):
        p = Path(data)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        suffix = p.suffix.lower()
        if suffix == ".parquet":
            return _from_parquet(str(p))
        if suffix == ".csv":
            return _from_csv_file(str(p))
        if suffix in (".json", ".jsonl"):
            return _from_json_file(str(p))
        raise ValueError(
            f"Unsupported file extension '{suffix}'. "
            "Supported: .parquet, .csv, .json, .jsonl"
        )

    # --- pandas DataFrame ---
    pd = _try_import("pandas")
    if pd:
        import pandas as pd_mod
        if isinstance(data, pd_mod.DataFrame):
            return _from_pandas(data)

    # --- polars DataFrame / LazyFrame ---
    pl = _try_import("polars")
    if pl:
        import polars as pl_mod
        if isinstance(data, (pl_mod.DataFrame, pl_mod.LazyFrame)):
            return _from_polars(data)

    # --- pyarrow Table ---
    pa = _try_import("pyarrow")
    if pa:
        import pyarrow as pa_mod
        if isinstance(data, pa_mod.Table):
            return _from_arrow_table(data)

    # --- DuckDB relation ---
    duck = _try_import("duckdb")
    if duck:
        import duckdb as ddb
        if isinstance(data, ddb.DuckDBPyRelation):
            return _from_duckdb(data)

    raise TypeError(
        f"Unsupported data type: {type(data).__name__}.\n"
        "Supported types: list[dict], pandas.DataFrame, polars.DataFrame, "
        "polars.LazyFrame, pyarrow.Table, duckdb.DuckDBPyRelation, "
        "or a file path str (.parquet / .csv / .json).\n"
        "For SQL: pass the SQL string as `data` with engine= (SQLAlchemy) "
        "or db= (SQLite)."
    )


# ===========================================================================
# Jupyter-aware QualityReport wrapper
# ===========================================================================

class RichQualityReport:
    """
    Wraps QualityReport and adds:
      - .show()         — pretty-prints in terminal OR renders HTML in Jupyter
      - ._repr_html_()  — Jupyter auto-renders as an HTML table
      - Passthrough to all original QualityReport attributes
    """

    _SEVERITY_COLOR = {
        "CRITICAL": "#c0392b",
        "WARNING":  "#e67e22",
        "INFO":     "#2980b9",
    }
    _TIER_COLOR = {
        "LITE":     "#27ae60",
        "STANDARD": "#f39c12",
        "ADVANCED": "#8e44ad",
    }

    def __init__(self, report: QualityReport) -> None:
        self._report = report

    # ---- passthrough ---------------------------------------------------------

    def __getattr__(self, name: str):
        return getattr(self._report, name)

    # ---- terminal ------------------------------------------------------------

    def show(self) -> None:
        """Auto-detects environment: renders HTML in Jupyter, text in terminal."""
        if _is_jupyter():
            from IPython.display import display, HTML
            display(HTML(self._repr_html_()))
        else:
            print(self._report.summary())

    # ---- Jupyter HTML --------------------------------------------------------

    def _repr_html_(self) -> str:
        r = self._report
        passed_pct = r.success_rate * 100
        bar_color = "#27ae60" if passed_pct == 100 else (
            "#e67e22" if passed_pct >= 60 else "#c0392b")

        # ── header card ──
        header = f"""
        <div style="
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            border: 1px solid #e1e4e8;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            background: #fafafa;
        ">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
              <span style="font-size:16px; font-weight:600; color:#24292e;">
                🔍 {r.pipeline_name}
              </span>
              <span style="font-size:12px; color:#6a737d; margin-left:10px;">
                {r.ran_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
              </span>
            </div>
            <div style="display:flex; gap:16px; font-size:13px;">
              <span>Total <strong>{len(r.results)}</strong></span>
              <span style="color:#27ae60;">✅ <strong>{len(r.passed)}</strong></span>
              <span style="color:#c0392b;">❌ <strong>{len(r.failed)}</strong></span>
            </div>
          </div>
          <div style="margin-top:10px;">
            <div style="display:flex; justify-content:space-between; font-size:12px; color:#6a737d; margin-bottom:3px;">
              <span>Pass rate</span><span>{passed_pct:.0f}%</span>
            </div>
            <div style="background:#e1e4e8; border-radius:4px; height:8px; overflow:hidden;">
              <div style="
                width:{passed_pct:.1f}%; height:100%;
                background:{bar_color}; border-radius:4px;
                transition: width 0.4s ease;
              "></div>
            </div>
          </div>
        </div>
        """

        # ── results table ──
        rows_html = ""
        for res in r.results:
            icon = "✅" if res.passed else "❌"
            tier_color = self._TIER_COLOR.get(res.tier.value, "#555")
            sev_color = self._SEVERITY_COLOR.get(res.severity.value, "#555")
            detail_html = ""

            if not res.passed and res.details:
                items = list(res.details.items())[:3]
                detail_lines = "".join(
                    f"<div style='margin-top:2px;'>"
                    f"<span style='color:#6a737d;'>↳ {k}:</span> "
                    f"<code style='font-size:11px;'>{str(v)[:120]}</code></div>"
                    for k, v in items
                )
                detail_html = f"<div style='font-size:11px; margin-top:4px;'>{detail_lines}</div>"

            rows_html += f"""
            <tr style="border-bottom:1px solid #f0f0f0;">
              <td style="padding:8px 10px; font-size:16px; text-align:center;">{icon}</td>
              <td style="padding:8px 10px; font-family:monospace; font-size:13px; color:#24292e;">
                {res.check_name}
              </td>
              <td style="padding:8px 10px;">
                <span style="
                  background:{tier_color}20; color:{tier_color};
                  border:1px solid {tier_color}40;
                  border-radius:4px; padding:2px 6px; font-size:11px; font-weight:500;
                ">{res.tier.value}</span>
              </td>
              <td style="padding:8px 10px;">
                <span style="
                  background:{sev_color}20; color:{sev_color};
                  border:1px solid {sev_color}40;
                  border-radius:4px; padding:2px 6px; font-size:11px; font-weight:500;
                ">{res.severity.value}</span>
              </td>
              <td style="padding:8px 10px; font-size:13px; color:#24292e;">
                {res.message}
                {detail_html}
              </td>
            </tr>
            """

        table = f"""
        <div style="border:1px solid #e1e4e8; border-radius:10px; overflow:hidden;">
          <table style="width:100%; border-collapse:collapse; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <thead>
              <tr style="background:#f6f8fa; font-size:12px; color:#6a737d; text-transform:uppercase; letter-spacing:.04em;">
                <th style="padding:8px 10px; text-align:center; width:40px;"></th>
                <th style="padding:8px 10px; text-align:left;">Check</th>
                <th style="padding:8px 10px; text-align:left;">Tier</th>
                <th style="padding:8px 10px; text-align:left;">Severity</th>
                <th style="padding:8px 10px; text-align:left;">Message</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """

        return header + table

    def __repr__(self) -> str:
        return self._report.summary()


# ===========================================================================
# Main facade — check()
# ===========================================================================

def check(
    data: Any,
    *,
    tier:          str | None = None,
    checks:        list[str] | None = None,
    pipeline_name: str = "dq_pipeline",
    fail_fast:     bool = False,
    config:        str | dict | None = None,
    sql:           str | None = None,
    engine=None,
    db:            str | None = None,
    # convenience kwargs passed straight to pipeline.run()
    **kwargs: Any,
) -> RichQualityReport:
    """
    Run data quality checks on any data format and return a RichQualityReport.

    Parameters
    ----------
    data : any supported format
        pandas DataFrame, Polars DataFrame/LazyFrame, PyArrow Table,
        DuckDB relation, file path (.parquet / .csv / .json),
        SQL string (with engine= or db=), or list[dict].
    tier : {"lite", "standard", "advanced"}, optional
        Run a full cumulative tier. Mutually exclusive with `checks`.
    checks : list[str], optional
        Run specific checks by name. Mutually exclusive with `tier`.
    pipeline_name : str
        Name shown in the report. Default: "dq_pipeline".
    fail_fast : bool
        Stop after the first CRITICAL failure. Default: False.
    config : str or dict, optional
        Path to a config.yaml file or a plain dict of check kwargs.
        Keys are merged with any extra **kwargs.
    sql : str, optional
        SQL query string. Requires `engine` or `db`.
    engine : sqlalchemy.Engine, optional
        SQLAlchemy engine for SQL execution.
    db : str, optional
        SQLite file path or ":memory:" for SQL execution.
    **kwargs
        Any additional keyword arguments are forwarded to every check's
        .run() method (e.g. pk_column="id", ranges={"age": (0, 120)}).

    Returns
    -------
    RichQualityReport
        Wraps QualityReport. Call .show() to display or let Jupyter
        auto-render it as an HTML table.

    Examples
    --------
    >>> report = check(df, tier="lite", pk_column="id")
    >>> report.show()

    >>> report = check("orders.parquet", tier="standard", config="config.yaml")
    >>> report.success_rate
    0.923

    >>> # fail fast, stop on first critical error
    >>> report = check(df, tier="advanced", fail_fast=True)
    """
    if tier is not None and checks is not None:
        raise ValueError("Specify either `tier` or `checks`, not both.")
    if tier is None and checks is None:
        raise ValueError(
            "Specify either `tier` ('lite'/'standard'/'advanced') or `checks`.")

    # ── normalize data ───────────────────────────────────────────────────────
    rows = normalize(data, sql=sql, engine=engine, db=db)

    # ── load config ──────────────────────────────────────────────────────────
    run_kwargs = _load_config(config)
    run_kwargs.update(kwargs)

    # ── build pipeline ───────────────────────────────────────────────────────
    check_names = _resolve_checks(tier, checks)
    pipeline = DataQualityPipeline(pipeline_name)
    for name in check_names:
        if name not in REGISTRY:
            raise ValueError(
                f"Unknown check: '{name}'. "
                f"Available: {sorted(REGISTRY.keys())}"
            )
        pipeline.add(REGISTRY[name]())

    # ── run ──────────────────────────────────────────────────────────────────
    report = pipeline.run(rows, fail_fast=fail_fast, **run_kwargs)
    return RichQualityReport(report)


# ===========================================================================
# Convenience tier shortcuts
# ===========================================================================

def check_lite(data: Any, **kwargs) -> RichQualityReport:
    """Shortcut: run the 5 Lite checks."""
    return check(data, tier="lite", **kwargs)


def check_standard(data: Any, **kwargs) -> RichQualityReport:
    """Shortcut: run Lite + Standard (13 checks)."""
    return check(data, tier="standard", **kwargs)


def check_advanced(data: Any, **kwargs) -> RichQualityReport:
    """Shortcut: run all 25 checks."""
    return check(data, tier="advanced", **kwargs)


# ===========================================================================
# Helpers
# ===========================================================================

def _resolve_checks(tier: str | None, checks: list[str] | None) -> list[str]:
    """Return ordered list of check names to run."""
    if checks:
        return checks
    tier = tier.lower()
    if tier == "lite":
        return list(TIER_MAP["lite"])
    if tier == "standard":
        return list(TIER_MAP["lite"] + TIER_MAP["standard"])
    if tier == "advanced":
        return list(TIER_MAP["lite"] + TIER_MAP["standard"] + TIER_MAP["advanced"])
    raise ValueError(
        f"Unknown tier: '{tier}'. Choose 'lite', 'standard', or 'advanced'.")


def _load_config(config: str | dict | None) -> dict:
    """Load config from a YAML file path or return dict as-is."""
    if config is None:
        return {}
    if isinstance(config, dict):
        return dict(config)
    # file path
    path = Path(config)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        import yaml
        raw = yaml.safe_load(path.read_text()) or {}
    except ImportError:
        raise ImportError(
            "PyYAML is required for YAML config files.  pip install pyyaml")
    return resolve_config(raw)


def resolve_config(cfg: dict) -> dict:
    """
    Post-process raw YAML config into types the pipeline expects.
    Mirrors the logic in cli/loaders.py so the facade is standalone.
    """
    from datetime import datetime, timezone
    out = dict(cfg)

    # latest_timestamp: "now" or ISO string → datetime
    ts = out.get("latest_timestamp")
    if ts == "now":
        out["latest_timestamp"] = datetime.now(timezone.utc)
    elif isinstance(ts, str):
        try:
            out["latest_timestamp"] = datetime.fromisoformat(
                ts).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # ranges: lists → tuples
    if "ranges" in out:
        out["ranges"] = {
            col: tuple(bounds) for col, bounds in out["ranges"].items()
        }

    # business_rules_expr → callable rules dict
    if "business_rules_expr" in out:
        out["rules"] = {
            name: safe_eval_rule(expr)
            for name, expr in out["business_rules_expr"].items()
        }

    # cross_rules_expr → callable cross_rules dict
    if "cross_rules_expr" in out:
        out["cross_rules"] = {
            name: safe_eval_rule(expr)
            for name, expr in out["cross_rules_expr"].items()
        }

    return out


def safe_eval_rule(expr: str):
    """
    Compile a safe string expression into a callable predicate.
    Supports: ==, !=, <, >, <=, >=, and, or, not.
    No eval() — uses ast.literal_eval-style safe comparison.
    """
    import ast

    _OPS = {
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
    }

    def _eval(node, row: dict):
        if isinstance(node, ast.Expression):
            return _eval(node.body, row)
        if isinstance(node, ast.BoolOp):
            values = [_eval(v, row) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand, row)
        if isinstance(node, ast.Compare):
            left = _eval(node.left, row)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval(comparator, row)
                if not _OPS[type(op)](left, right):
                    return False
            return True
        if isinstance(node, ast.Name):
            return row.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    tree = ast.parse(expr, mode="eval")

    def predicate(row: dict) -> bool:
        try:
            return bool(_eval(tree, row))
        except Exception:
            return False

    predicate.__doc__ = expr
    return predicate


def _is_jupyter() -> bool:
    """True when running inside a Jupyter / IPython kernel."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        return ip is not None and hasattr(ip, "kernel")
    except ImportError:
        return False


# ===========================================================================
# Introspection helpers (useful in notebooks)
# ===========================================================================

def list_checks() -> None:
    """Print all available checks grouped by tier."""
    for tier_name in ("lite", "standard", "advanced"):
        print(f"\n── {tier_name.upper()} ──")
        for name in TIER_MAP[tier_name]:
            cls = REGISTRY[name]
            print(f"  {name:<35} severity={cls().severity.value}")
    print()


def supported_formats() -> None:
    """Print all supported input data formats."""
    formats = [
        ("pandas.DataFrame",          "import pandas as pd; df = pd.read_csv(...)"),
        ("polars.DataFrame",          "import polars as pl; df = pl.read_parquet(...)"),
        ("polars.LazyFrame",          "pl.scan_parquet('data.parquet')"),
        ("pyarrow.Table",             "import pyarrow.parquet as pq; pq.read_table(...)"),
        ("duckdb.DuckDBPyRelation",   "conn.sql('SELECT * FROM table')"),
        (".parquet file path",        "check('data.parquet', tier='lite')"),
        (".csv file path",            "check('data.csv', tier='lite')"),
        (".json file path",           "check('data.json', tier='lite')"),
        ("SQLAlchemy + SQL string",   "check('SELECT ...', engine=engine, tier='lite')"),
        ("SQLite + SQL string",
         "check('SELECT ...', db='mydb.sqlite', tier='lite')"),
        ("list[dict]",                "check([{'id':1,...}], tier='lite')"),
    ]
    print(f"\n{'Format':<35} {'Example'}")
    print("─" * 75)
    for fmt, example in formats:
        print(f"  {fmt:<33} {example}")
    print()
