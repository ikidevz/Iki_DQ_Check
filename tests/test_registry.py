"""
test_registry.py — Tests for REGISTRY, TIER_MAP, and check class metadata.

Validates that the registry is complete, tiers are consistent,
all checks are instantiable, and severity/tier assignments are correct.
"""

from __future__ import annotations

import pytest

from Iki_DQ_Check import (
    REGISTRY,
    TIER_MAP,
    CheckTier,
    Severity,
    NullCheck,
    RegexCheck,
    DistributionCheck,
    ChecksumCheck,
)


# ===========================================================================
# Registry completeness
# ===========================================================================

class TestRegistryCompleteness:

    def test_registry_has_exactly_25_checks(self):
        assert len(REGISTRY) == 25, f"Expected 25 checks, got {len(REGISTRY)}"

    def test_all_registry_entries_are_instantiable(self):
        for name, cls in REGISTRY.items():
            instance = cls()
            assert hasattr(instance, "run"), f"{name} missing .run()"

    def test_all_registry_names_match_class_names(self):
        for name, cls in REGISTRY.items():
            assert cls.__name__ == name, (
                f"Registry key '{name}' does not match class name '{cls.__name__}'"
            )


# ===========================================================================
# TIER_MAP consistency
# ===========================================================================

class TestTierMap:

    def test_tier_map_has_all_three_tiers(self):
        assert set(TIER_MAP.keys()) == {"lite", "standard", "advanced"}

    def test_tier_map_covers_all_registry_entries(self):
        all_in_tiers = set(
            TIER_MAP["lite"] + TIER_MAP["standard"] + TIER_MAP["advanced"]
        )
        registry_keys = set(REGISTRY.keys())
        diff = all_in_tiers.symmetric_difference(registry_keys)
        assert not diff, f"Mismatch between TIER_MAP and REGISTRY: {diff}"

    def test_no_check_appears_in_multiple_tiers(self):
        all_names = TIER_MAP["lite"] + \
            TIER_MAP["standard"] + TIER_MAP["advanced"]
        assert len(all_names) == len(set(all_names)
                                     ), "Duplicate check name across tiers"

    def test_lite_has_5_checks(self):
        assert len(TIER_MAP["lite"]) == 5

    def test_standard_has_8_checks(self):
        assert len(TIER_MAP["standard"]) == 8

    def test_advanced_has_12_checks(self):
        assert len(TIER_MAP["advanced"]) == 12

    def test_all_tier_map_entries_exist_in_registry(self):
        for tier, names in TIER_MAP.items():
            for name in names:
                assert name in REGISTRY, f"'{name}' in TIER_MAP['{tier}'] not found in REGISTRY"


# ===========================================================================
# Severity assignments
# ===========================================================================

class TestSeverityAssignments:

    def test_null_check_is_critical(self):
        assert NullCheck().severity == Severity.CRITICAL

    def test_regex_check_is_warning(self):
        assert RegexCheck().severity == Severity.WARNING

    def test_distribution_check_is_info(self):
        assert DistributionCheck().severity == Severity.INFO

    def test_all_lite_checks_are_critical(self):
        for name in TIER_MAP["lite"]:
            check = REGISTRY[name]()
            assert check.severity == Severity.CRITICAL, (
                f"{name} should be CRITICAL but is {check.severity}"
            )


# ===========================================================================
# Tier assignments on check classes
# ===========================================================================

class TestTierAssignments:

    def test_null_check_tier_is_lite(self):
        assert NullCheck().tier == CheckTier.LITE

    def test_regex_check_tier_is_standard(self):
        assert RegexCheck().tier == CheckTier.STANDARD

    def test_checksum_check_tier_is_advanced(self):
        assert ChecksumCheck().tier == CheckTier.ADVANCED

    def test_all_lite_tier_map_entries_have_lite_tier(self):
        for name in TIER_MAP["lite"]:
            check = REGISTRY[name]()
            assert check.tier == CheckTier.LITE, (
                f"{name} is in TIER_MAP['lite'] but has tier {check.tier}"
            )

    def test_all_standard_tier_map_entries_have_standard_tier(self):
        for name in TIER_MAP["standard"]:
            check = REGISTRY[name]()
            assert check.tier == CheckTier.STANDARD, (
                f"{name} is in TIER_MAP['standard'] but has tier {check.tier}"
            )

    def test_all_advanced_tier_map_entries_have_advanced_tier(self):
        for name in TIER_MAP["advanced"]:
            check = REGISTRY[name]()
            assert check.tier == CheckTier.ADVANCED, (
                f"{name} is in TIER_MAP['advanced'] but has tier {check.tier}"
            )


# ===========================================================================
# Check.name property
# ===========================================================================

class TestCheckNameProperty:

    def test_check_name_matches_class_name(self):
        for name, cls in REGISTRY.items():
            assert cls().name == name, (
                f"check.name '{cls().name}' should equal registry key '{name}'"
            )
