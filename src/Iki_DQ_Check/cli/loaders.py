"""
Iki_DQ_Check/cli/loaders.py
============================
I/O and config-loading logic for the CLI.

Config is now Python-native (DQConfig dataclass) instead of YAML.
YAML is still accepted for backwards compatibility but deprecated.

Public API
----------
load_data(path)               -> list[dict]
load_config(source)           -> dict
    source can be:
        None               -> {}
        DQConfig instance  -> cfg.to_kwargs()
        str path to .py    -> imports and returns DQConfig.to_kwargs()
        str path to .yaml  -> legacy YAML load (deprecated, still works)
        dict               -> returned as-is
coerce(value)                -> int | float | str | None
resolve_config(cfg)          -> dict   (YAML post-processor, kept for compat)
safe_eval_rule(expr)         -> Callable[[dict], bool]
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import json
import operator as op_mod
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------

def load_data(path: str) -> list[dict]:
    """
    Load a .json or .csv file and return a list of row dicts.

    JSON shapes supported:
      - Top-level list:               [{...}, ...]
      - Dict with a recognised key:   {"data": [...]} / {"records": [...]}
                                      {"rows": [...]}  / {"items": [...]}

    CSV values are auto-coerced via coerce():
      - Empty string / "null" / "none" / "na"  -> None
      - Numeric strings                        -> int or float
      - Everything else                        -> str
    """
    from .runner import die

    p = Path(path)
    if not p.exists():
        die(f"Data file not found: {path}")

    suffix = p.suffix.lower()

    if suffix == ".json":
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in ("data", "records", "rows", "items"):
                if key in raw and isinstance(raw[key], list):
                    return raw[key]
        die(
            "JSON file must contain a top-level list, or a dict with a "
            "'data' / 'records' / 'rows' / 'items' key."
        )

    elif suffix == ".csv":
        rows: list[dict] = []
        reader = csv.DictReader(StringIO(p.read_text(encoding="utf-8-sig")))
        for row in reader:
            rows.append({k: coerce(v) for k, v in row.items()})
        return rows

    else:
        die(f"Unsupported file type '{suffix}'. Use .json or .csv")


# ---------------------------------------------------------------------------
# Config loader  —  Python-native, YAML-compatible
# ---------------------------------------------------------------------------

def load_config(source: Any) -> dict:
    """
    Load check configuration from any supported source and return a plain
    dict ready to unpack into pipeline.run(**cfg).

    Accepted sources
    ----------------
    None                    -> {}  (all checks use their defaults)
    DQConfig instance       -> cfg.to_kwargs()
    path to a .py file      -> the file must define a DQConfig named
                               'config' or 'cfg' at module level
    path to a .yaml file    -> legacy YAML load (deprecated but supported)
    dict                    -> returned as-is after resolve_config()

    Python config file example (my_config.py):
    -------------------------------------------
        from Iki_DQ_Check.config import DQConfig

        config = DQConfig(
            pk_column="order_id",
            ranges={"amount": (0, None)},
            allowed={"status": ["active", "inactive"]},
            rules={
                "amount_positive": lambda r: (r.get("amount") or 0) > 0,
            },
        )
    -------------------------------------------

    CLI usage:
        iki-dq-check --tier lite --file data.json --config my_config.py
    """
    from .runner import die

    # None / empty
    if source is None or source == "":
        return {}

    # DQConfig instance passed directly (facade / library usage)
    try:
        from ..config import DQConfig
        if isinstance(source, DQConfig):
            return source.to_kwargs()
    except ImportError:
        pass

    # Plain dict
    if isinstance(source, dict):
        return resolve_config(source)

    # File path
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            die(f"Config file not found: {source}")

        suffix = p.suffix.lower()

        # ── Python config file (.py) ──────────────────────────────────────
        if suffix == ".py":
            return _load_python_config(p, die)

        # ── YAML config file (.yaml / .yml) — legacy ──────────────────────
        if suffix in (".yaml", ".yml"):
            return _load_yaml_config(p, die)

        die(
            f"Unsupported config format '{suffix}'. "
            "Use a .py file (recommended) or .yaml (legacy)."
        )

    die(f"Unsupported config source type: {type(source).__name__}")


def _load_python_config(path: Path, die) -> dict:
    """
    Import a .py config file and extract the DQConfig from it.

    The file must define a module-level variable named 'config' or 'cfg'
    that is a DQConfig instance. Any other name is also accepted if it is
    the only DQConfig in the module.
    """
    try:
        from ..config import DQConfig
    except ImportError:
        die("Could not import DQConfig — ensure the package is installed.")

    spec = importlib.util.spec_from_file_location("_dq_user_config", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        die(f"Error loading config file '{path}': {e}")

    # Look for named variable first
    for name in ("config", "cfg", "CONFIG", "CFG"):
        obj = getattr(mod, name, None)
        if isinstance(obj, DQConfig):
            return obj.to_kwargs()

    # Fall back: any DQConfig instance in the module
    for attr in vars(mod).values():
        if isinstance(attr, DQConfig):
            return attr.to_kwargs()

    die(
        f"Config file '{path}' must define a DQConfig instance named "
        "'config' or 'cfg' at module level.\n\n"
        "  Example:\n"
        "    from Iki_DQ_Check.config import DQConfig\n"
        "    config = DQConfig(pk_column='id', ...)"
    )


def _load_yaml_config(path: Path, die) -> dict:
    """Load a legacy YAML config file. Still works, but .py is preferred."""
    try:
        import yaml
    except ImportError:
        die(
            "PyYAML is required for .yaml config files.\n"
            "  pip install pyyaml\n"
            "  Or switch to a Python config file (.py) — no extra deps needed."
        )
    with path.open(encoding="utf-8") as f:
        cfg: dict = yaml.safe_load(f) or {}
    return resolve_config(cfg)


# ---------------------------------------------------------------------------
# Config resolver  (YAML post-processor — kept for backwards compatibility)
# ---------------------------------------------------------------------------

def resolve_config(cfg: dict) -> dict:
    """
    Post-process a raw dict (from YAML or passed directly) into the types
    the pipeline expects.

    Transformations
    ---------------
    latest_timestamp: "now"                 -> datetime.now(utc)
    latest_timestamp: "2024-09-10T01:00:00" -> datetime (UTC)
    ranges: {"age": [0, 120]}               -> {"age": (0, 120)}
    business_rules_expr: {name: expr_str}   -> rules: {name: Callable}
    cross_rules_expr: {name: expr_str}      -> cross_rules: {name: Callable}

    Python-native DQConfig dicts skip this — types are already correct.
    """
    # Freshness timestamp
    if "latest_timestamp" in cfg:
        val = cfg["latest_timestamp"]
        if val == "now":
            cfg["latest_timestamp"] = datetime.now(timezone.utc)
        elif isinstance(val, str):
            cfg["latest_timestamp"] = datetime.fromisoformat(val).replace(
                tzinfo=timezone.utc
            )

    # Ranges: list -> tuple
    if "ranges" in cfg and isinstance(cfg["ranges"], dict):
        cfg["ranges"] = {k: tuple(v) for k, v in cfg["ranges"].items()}

    # Business rules: string expressions -> callable predicates
    if "business_rules_expr" in cfg:
        cfg["rules"] = {
            name: safe_eval_rule(expr)
            for name, expr in cfg.pop("business_rules_expr").items()
        }

    # Cross-column rules: same treatment
    if "cross_rules_expr" in cfg:
        cfg["cross_rules"] = {
            name: safe_eval_rule(expr)
            for name, expr in cfg.pop("cross_rules_expr").items()
        }

    return cfg


# ---------------------------------------------------------------------------
# Safe expression compiler
# ---------------------------------------------------------------------------

def safe_eval_rule(expr: str) -> Callable[[dict], bool]:
    """
    Compile a simple rule expression string into a row predicate callable.

    Uses Python's ast module — no eval() is ever called.

    Supported syntax
    ----------------
    Column references:  salary, age, name, status
    Comparisons:        ==  !=  <  >  <=  >=
    Boolean operators:  and  or  not
    Literals:           integers, floats, strings

    Returns False (never raises) on any runtime error.
    """
    _OPS: dict[type, Callable] = {
        ast.Eq:    op_mod.eq,
        ast.NotEq: op_mod.ne,
        ast.Lt:    op_mod.lt,
        ast.LtE:   op_mod.le,
        ast.Gt:    op_mod.gt,
        ast.GtE:   op_mod.ge,
    }

    def _eval(node: ast.AST, row: dict) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body, row)
        if isinstance(node, ast.BoolOp):
            values = [_eval(v, row) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand, row)
        if isinstance(node, ast.Compare):
            left = _eval(node.left, row)
            for cmp_op, right_node in zip(node.ops, node.comparators):
                right = _eval(right_node, row)
                fn = _OPS.get(type(cmp_op))
                if fn is None:
                    raise ValueError(
                        f"Unsupported operator: {type(cmp_op).__name__}")
                if not fn(left, right):
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


# ---------------------------------------------------------------------------
# CSV value coercion
# ---------------------------------------------------------------------------

def coerce(value: str) -> int | float | str | None:
    """
    Best-effort type coercion for raw CSV string values.

    ""  /  "null"  /  "none"  /  "na"  ->  None
    Parseable as int                    ->  int
    Parseable as float                  ->  float
    Anything else                       ->  str
    """
    if value == "" or value.strip().lower() in ("null", "none", "na", "n/a", "nan"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
