"""
Iki_DQ_Check/cli/args.py
=========================
Argument parser definition for the Data Quality CLI.

Public API
----------
build_parser() -> argparse.ArgumentParser
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the CLI argument parser.

    Flags
    -----
    --list              Print all checks grouped by tier and exit.
    --tier TIER         Run a cumulative tier: lite | standard | advanced.
                        Accepts exactly one value per run.
    --check CHECK_NAME  Run a specific check by class name. Repeatable.
    --file PATH         Path to input data file (.json or .csv).
    --config PATH       Path to a Python config file (.py) or legacy YAML (.yaml).
    --output PATH       Save JSON report to this path.
    --fail-fast         Stop pipeline on first CRITICAL failure.
    --pipeline-name N   Label for this run (default: dq_pipeline).
    """
    parser = argparse.ArgumentParser(
        prog="iki-dq-check",
        description="Data Quality Framework — validate data from the CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  iki-dq-check --list
  iki-dq-check --tier lite     --file data.json --config my_config.py
  iki-dq-check --tier standard --file data.json --config my_config.py
  iki-dq-check --tier advanced --file data.json --config my_config.py --output report.json
  iki-dq-check --check NullCheck --file data.json --config my_config.py
  iki-dq-check --check NullCheck --check RegexCheck --file data.json
  iki-dq-check --tier lite --file data.json --config my_config.py --fail-fast
  iki-dq-check --tier lite --file data.json --config my_config.py --pipeline-name orders_daily

config file (my_config.py):
  from Iki_DQ_Check.config import DQConfig

  config = DQConfig(
      pk_column="id",
      ranges={"salary": (0, None)},
      allowed={"status": ["active", "inactive"]},
      rules={
          "salary_positive": lambda r: (r.get("salary") or 0) > 0,
      },
  )
        """,
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available checks grouped by tier and exit",
    )
    parser.add_argument(
        "--tier",
        action="append",
        metavar="TIER",
        choices=["lite", "standard", "advanced"],
        help="Run a cumulative tier: lite | standard | advanced  (one value only)",
    )
    parser.add_argument(
        "--check",
        action="append",
        metavar="CHECK_NAME",
        help="Run a specific check by name. Repeatable: --check NullCheck --check RegexCheck",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Path to input data file (.json or .csv)",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help=(
            "Path to a Python config file (.py, recommended) "
            "or legacy YAML file (.yaml). "
            "The .py file must define a DQConfig instance named 'config' or 'cfg'."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Save a JSON report to this path",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop the pipeline after the first CRITICAL failure",
    )
    parser.add_argument(
        "--pipeline-name",
        metavar="NAME",
        default="dq_pipeline",
        help="Label for this pipeline run (default: dq_pipeline)",
    )

    return parser
