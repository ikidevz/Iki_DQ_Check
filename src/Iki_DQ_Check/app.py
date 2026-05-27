from .cli import (
    build_parser,
    print_list,
    die,
    load_data,
    load_config,
    build_pipeline,
    print_summary,
    save_report
)
from .cli.output import CYAN, DIM

import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _normalize_arg(value):
    """
    argparse may return:
      - None
      - str
      - list[str]
    We normalize everything to list[str]
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --list
    if args.list:
        print_list()
        sys.exit(0)

    # Validate required file
    if not args.file:
        die("--file is required. Use --list to see available checks.")

    # Must have at least tier or check
    if not args.tier and not args.check:
        die("Specify at least --tier or --check. Use --list to see options.")

    # ✅ FIX: normalize argparse inputs (THIS WAS BREAKING EVERYTHING)
    tiers = _normalize_arg(args.tier)
    checks = _normalize_arg(args.check)

    # Load
    print(CYAN(f"\n  ▶ Loading data from: {args.file}"))
    data = load_data(args.file)
    print(DIM(f"    {len(data)} rows loaded"))

    print(CYAN(f"  ▶ Loading config from: {args.config or '(none)'}"))
    cfg = load_config(args.config)

    # Build pipeline
    print(
        CYAN(
            f"  ▶ Building pipeline: tiers={tiers or '—'}, checks={checks or '—'}"
        )
    )

    pipeline = build_pipeline(args.pipeline_name, tiers, checks)

    # Run
    print(CYAN(f"  ▶ Running {args.pipeline_name}…"))
    report = pipeline.run(data, fail_fast=args.fail_fast, **cfg)

    # Print results (THIS IS WHAT YOUR TESTS EXPECT)
    print_summary(report)

    # Save output if requested
    if args.output:
        save_report(report, args.output)

    # Exit code logic
    critical_failures = [
        r for r in report.failed if r.severity.value == "CRITICAL"
    ]

    sys.exit(1 if critical_failures else 0)


if __name__ == "__main__":
    main()
