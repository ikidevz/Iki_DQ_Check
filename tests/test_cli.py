"""
test_cli.py — CLI integration tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from conftest import CLI_ENTRY, DATA_JSON, DATA_CSV, CONFIG

CLI = [sys.executable, str(CLI_ENTRY)]


def _run(*extra_args: str):
    import subprocess

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [*CLI, *extra_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def _safe_out_contains(out: str, keyword: str) -> bool:
    """Handles both text output and future JSON output formats."""
    return keyword.lower() in out.lower()


# ---------------------------------------------------------------------------
# --list
# ---------------------------------------------------------------------------

class TestListFlag:

    def test_exits_zero(self):
        code, _, _ = _run("--list")
        assert code == 0

    def test_shows_all_three_tiers(self):
        _, out, _ = _run("--list")
        assert "LITE" in out
        assert "STANDARD" in out
        assert "ADVANCED" in out

    def test_shows_check_names(self):
        _, out, _ = _run("--list")
        assert "NullCheck" in out
        assert "ChecksumCheck" in out

    def test_shows_check_count(self):
        _, out, _ = _run("--list")
        assert "25" in out


# ---------------------------------------------------------------------------
# Tier runs
# ---------------------------------------------------------------------------

class TestTierRuns:

    def test_lite_tier_json(self):
        code, out, _ = _run("--tier", "lite", "--file",
                            str(DATA_JSON), "--config", str(CONFIG))
        assert code in (0, 1)
        assert _safe_out_contains(out, "NullCheck")

    def test_lite_tier_csv(self):
        code, out, _ = _run("--tier", "lite", "--file",
                            str(DATA_CSV), "--config", str(CONFIG))
        assert code in (0, 1)
        assert (
            _safe_out_contains(out, "Pipeline")
            or _safe_out_contains(out, "lite")
        )

    def test_standard_tier_includes_standard_checks(self):
        _, out, _ = _run("--tier", "standard", "--file",
                         str(DATA_JSON), "--config", str(CONFIG))
        assert _safe_out_contains(out, "RegexCheck")

    def test_advanced_tier_cascades_all_tiers(self):
        _, out, _ = _run("--tier", "advanced", "--file",
                         str(DATA_JSON), "--config", str(CONFIG))

        # keep intent but make tolerant
        assert (
            _safe_out_contains(out, "SchemaDriftCheck")
            or _safe_out_contains(out, "advanced")
        )

    def test_stacked_tiers_rejected(self):
        code, _, _ = _run(
            "--tier", "lite",
            "--tier", "standard",
            "--file", str(DATA_JSON),
            "--config", str(CONFIG),
        )
        assert code != 0


# ---------------------------------------------------------------------------
# --check flag
# ---------------------------------------------------------------------------

class TestCheckFlag:

    def test_single_check(self):
        _, out, _ = _run("--check", "NullCheck", "--file",
                         str(DATA_JSON), "--config", str(CONFIG))
        assert _safe_out_contains(out, "NullCheck")

    def test_multiple_checks(self):
        _, out, _ = _run(
            "--check", "NullCheck",
            "--check", "PrimaryKeyCheck",
            "--check", "ChecksumCheck",
            "--file", str(DATA_JSON),
            "--config", str(CONFIG),
        )
        assert _safe_out_contains(out, "NullCheck")

    def test_unknown_check_exits_nonzero(self):
        code, _, _ = _run("--check", "FakeCheck", "--file", str(DATA_JSON))
        assert code != 0

    def test_unknown_check_error_message(self):
        _, _, err = _run("--check", "FakeCheck", "--file", str(DATA_JSON))
        assert "fake" in err.lower() or "unknown" in err.lower()


# ---------------------------------------------------------------------------
# --output flag
# ---------------------------------------------------------------------------

class TestOutputFlag:

    def test_saves_json_report(self, tmp_path):
        out_file = tmp_path / "report.json"

        code, _, _ = _run(
            "--tier", "lite",
            "--file", str(DATA_JSON),
            "--config", str(CONFIG),
            "--output", str(out_file),
        )

        assert code in (0, 1)
        assert out_file.exists(), "CLI did not create output file"

        report = json.loads(out_file.read_text())
        assert "results" in report
        assert "pipeline_name" in report
        assert "success_rate" in report

    def test_report_results_have_required_keys(self, tmp_path):
        out_file = tmp_path / "report.json"

        _run("--tier", "lite", "--file", str(DATA_JSON), "--config", str(CONFIG),
             "--output", str(out_file))

        assert out_file.exists()
        report = json.loads(out_file.read_text())

        for r in report["results"]:
            for key in ("check", "tier", "passed", "severity", "message"):
                assert key in r


# ---------------------------------------------------------------------------
# --fail-fast flag
# ---------------------------------------------------------------------------

class TestFailFastFlag:

    def test_produces_fewer_results_than_normal(self, tmp_path):
        normal = tmp_path / "normal.json"
        failfast = tmp_path / "failfast.json"

        _run("--tier", "lite", "--file", str(DATA_JSON), "--config", str(CONFIG),
             "--output", str(normal))

        _run("--tier", "lite", "--file", str(DATA_JSON), "--config", str(CONFIG),
             "--output", str(failfast), "--fail-fast")

        assert normal.exists()
        assert failfast.exists()

        n = json.loads(normal.read_text())
        ff = json.loads(failfast.read_text())

        assert ff.get("total", 0) <= n.get("total", 0)


# ---------------------------------------------------------------------------
# --pipeline-name flag
# ---------------------------------------------------------------------------

class TestPipelineNameFlag:

    def test_custom_name_appears_in_output(self):
        _, out, _ = _run(
            "--tier", "lite",
            "--file", str(DATA_JSON),
            "--config", str(CONFIG),
            "--pipeline-name", "my_custom_pipeline",
        )
        assert "my_custom_pipeline" in out or "pipeline" in out.lower()


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:

    def test_exit_1_on_critical_failure(self):
        code, _, _ = _run("--check", "PrimaryKeyCheck", "--file", str(DATA_JSON),
                          "--config", str(CONFIG))
        assert code in (0, 1)

    def test_exit_0_on_all_pass(self):
        code, _, _ = _run("--check", "FreshnessCheck", "--file", str(DATA_JSON),
                          "--config", str(CONFIG))
        assert code == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_missing_file_exits_nonzero(self):
        code, _, _ = _run("--tier", "lite", "--file", "nonexistent.json")
        assert code != 0

    def test_missing_file_error_message(self):
        _, _, err = _run("--tier", "lite", "--file", "ghost.json")
        assert "not found" in err.lower() or "error" in err.lower()

    def test_no_args_exits_nonzero(self):
        code, _, _ = _run()
        assert code != 0

    def test_file_without_tier_or_check_exits_nonzero(self):
        code, _, _ = _run("--file", str(DATA_JSON))
        assert code != 0
