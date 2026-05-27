from .output import RED
from ..core.pipeline import DataQualityPipeline
from ..core.pipeline import TIER_MAP, REGISTRY

import sys


def die(msg: str) -> None:
    print(RED(f"\n  ✘ Error: {msg}\n"), file=sys.stderr)
    sys.exit(1)


def build_pipeline(name: str, tiers: list[str], checks: list[str]) -> DataQualityPipeline:
    """
    Build pipeline from a single tier name + optional explicit check names.
    --tier is strictly one value — no repeating allowed.

    Tier cascade (cumulative upward):
      --tier lite     → LITE only                       (5 checks)                      (5 checks)
      --tier standard → LITE + STANDARD                  (13 checks)                  (13 checks)
      --tier advanced → LITE + STANDARD + ADVANCED       (25 checks)            (25 checks)
    """
    pipeline = DataQualityPipeline(name)
    seen: set[str] = set()

    if len(tiers) > 1:
        die(f"--tier only accepts one value. Got: {tiers}\n"
            f"  Use --tier lite, --tier standard, or --tier advanced.")

    TIER_ORDER = ["lite", "standard", "advanced"]

    for tier in tiers:
        tier = tier.lower()
        if tier not in TIER_MAP:
            die(f"Unknown tier '{tier}'. Valid: lite, standard, advanced")

        # Cascade: include all tiers up to and including the chosen one
        cutoff = TIER_ORDER.index(tier)
        for t in TIER_ORDER[: cutoff + 1]:
            for check_name in TIER_MAP[t]:
                if check_name not in seen:
                    seen.add(check_name)
                    pipeline.add(REGISTRY[check_name]())

    # Explicit --check flags (deduplicated, unknown = error)
    for check_name in checks:
        if check_name not in REGISTRY:
            die(
                f"Unknown check '{check_name}'.\n"
                f"Run with --list to see all available checks."
            )
        if check_name not in seen:
            seen.add(check_name)
            pipeline.add(REGISTRY[check_name]())

    if not seen:
        die("No checks selected. Use --tier or --check.")

    return pipeline
