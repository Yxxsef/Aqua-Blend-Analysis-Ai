"""
test_ai_pipeline.py — Task 72 (Sprint 3)

Runs the shared fixture pack in AI/integration_tests/fixtures/ through the
real AI-stream modules, so every module is tested against the same
representative cases instead of unrelated one-off examples per task.

Run everything with one command from the repo root:
    pytest AI/integration_tests/test_ai_pipeline.py -v

This imports the real modules directly from their existing locations
(AI/evaluation, AI/results, AI/explanations) rather than duplicating any
of their logic here — this file only orchestrates and asserts.
"""
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

for _rel in ("AI/evaluation", "AI/results", "AI/explanations"):
    _path = os.path.join(_REPO_ROOT, _rel)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from kpi_calculator import calculate_kpis          # AI/evaluation
from kpi_gate import evaluate_gate                 # AI/evaluation
from sensitivity_ranking import rank_sensitivities  # AI/results
from llm_validator import validate_llm_output       # AI/explanations
from diagnostics_adapter import (                   # AI/explanations (Task 71)
    build_infeasibility_context,
    render_diagnostics_section,
)


def _load(*parts):
    with open(os.path.join(_FIXTURES, *parts)) as f:
        return json.load(f)


def _results_json_fixtures():
    folder = os.path.join(_FIXTURES, "results_json")
    return sorted(f for f in os.listdir(folder) if f.endswith(".json"))


def _llm_reporting_fixtures():
    folder = os.path.join(_FIXTURES, "llm_reporting")
    return sorted(f for f in os.listdir(folder) if f.endswith(".json"))


# ---------------------------------------------------------------------------
# results_json/ — every fixture must survive calculate_kpis + evaluate_gate
# without raising, regardless of how broken/incomplete/malformed it is.
# ---------------------------------------------------------------------------
class TestResultsJsonFixturesSurviveThePipeline:
    """KPI_Set.md's own design rule is 'never estimate a missing value' —
    the practical version of that rule is 'never crash on missing data
    either'. Every fixture here, including the deliberately malformed one,
    must produce a KPIReport and a GateResult without raising.
    """

    @pytest.mark.parametrize("filename", _results_json_fixtures())
    def test_fixture_does_not_crash_the_kpi_pipeline(self, filename):
        data = _load("results_json", filename)
        report = calculate_kpis(data)  # must not raise
        gate = evaluate_gate(report)   # must not raise
        assert gate.overall_status in ("PASS", "FAIL", "UNABLE_TO_EVALUATE")

    def test_optimal_provisional_real_passes(self):
        data = _load("results_json", "optimal_provisional_real.json")
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "PASS"
        # This scenario's sources are all flagged has_estimated_values=true —
        # confirms the "provisional" half of the optimal/provisional pairing.
        assert all(
            s["has_estimated_values"] for s in data["data_flags"]["sources"]
        )

    def test_optimal_measured_synthetic_passes(self):
        data = _load("results_json", "optimal_measured_synthetic.json")
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "PASS"
        # Confirms the "measured" half — every source has_estimated_values=false.
        assert not any(
            s["has_estimated_values"] for s in data["data_flags"]["sources"]
        )

    def test_infeasible_status_only_fails(self):
        data = _load("results_json", "infeasible_status_only_synthetic.json")
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "FAIL"

    @pytest.mark.parametrize("filename", [
        "failed_solver_error_synthetic.json",
        "failed_solver_unbounded_synthetic.json",
    ])
    def test_failed_solver_statuses_fail(self, filename):
        data = _load("results_json", filename)
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "FAIL"

    def test_time_limit_without_incumbent_is_unable_to_evaluate(self):
        data = _load("results_json", "failed_solver_time_limit_no_incumbent_synthetic.json")
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "UNABLE_TO_EVALUATE"

    def test_invalid_input_missing_status_is_unable_to_evaluate(self):
        data = _load("results_json", "invalid_input_malformed_synthetic.json")
        report = calculate_kpis(data)
        gate = evaluate_gate(report)
        assert gate.overall_status == "UNABLE_TO_EVALUATE"


# ---------------------------------------------------------------------------
# sensitivity/ — the one real fixture must be exactly reproducible by
# re-running the real optimal_provisional_real.json input through the real
# rank_sensitivities() function. This is a genuine end-to-end check, not
# just a shape check on stored output.
# ---------------------------------------------------------------------------
class TestSensitivityFixtureIsReproducible:

    def test_unsupported_real_fixture_matches_live_function_output(self):
        source_input = _load("results_json", "optimal_provisional_real.json")
        expected_output = _load("sensitivity", "unsupported_real.json")
        actual_output = rank_sensitivities(source_input)
        assert actual_output == expected_output

    def test_unsupported_reason_explains_why_not_ranked(self):
        expected_output = _load("sensitivity", "unsupported_real.json")
        assert expected_output["status"] == "INSUFFICIENT_DATA"
        assert expected_output["ranking"] == []
        assert len(expected_output["verified_entries"]) > 0


# ---------------------------------------------------------------------------
# llm_reporting/ — every fixture pair must produce the documented
# critical_result (and rule, where specified) from the real validator.
# ---------------------------------------------------------------------------
class TestLlmReportingFixturesMatchExpectedValidatorResult:

    @pytest.mark.parametrize("filename", _llm_reporting_fixtures())
    def test_fixture_matches_its_documented_expected_result(self, filename):
        fixture = _load("llm_reporting", filename)
        result = validate_llm_output(
            fixture["deterministic_report"], fixture["llm_output"]
        )
        assert result.critical_result == fixture["expected_critical_result"], (
            f"{filename}: expected {fixture['expected_critical_result']}, "
            f"got {result.critical_result}"
        )
        expected_rule = fixture.get("expected_rule")
        if expected_rule:
            fired_rules = {f.rule for f in result.critical_failures}
            assert expected_rule in fired_rules, (
                f"{filename}: expected rule {expected_rule} to fire, "
                f"got {fired_rules}"
            )

    def test_accepted_rewrite_is_the_real_correct_rewrite_fixture(self):
        fixture = _load("llm_reporting", "accepted_rewrite_real.json")
        assert "scenario_2026_07_17_001" in fixture["deterministic_report"]
        assert fixture["expected_critical_result"] == "PASS"

    def test_validator_failure_fixture_is_genuinely_truncated(self):
        """Regression guard: this fixture's whole point is that it is a real,
        captured, truncated model output (see LLM_Live_Run_Notes.md and PR #46).
        If someone 'fixes' the fixture text to be complete, this test should
        fail loudly rather than silently start passing for the wrong reason.
        """
        fixture = _load("llm_reporting", "validator_failure_truncated_real.json")
        assert not fixture["llm_output"].rstrip().endswith((".", "!", "?"))


# ---------------------------------------------------------------------------
# diagnostics/ — Task 71's diagnostics_adapter.py. Note: the payload shape
# here is explicitly PROVISIONAL per Infeasibility_AI_Interface.md section 3
# ("sourced directly from integration_v1_3.md section 20's own 'conceptual'
# example... treat every field name as subject to change"). The module and
# its outcome logic are real and tested; the payload shape it's built
# against is not yet confirmed by the wider team.
# ---------------------------------------------------------------------------
class TestDiagnosticsFixturesMatchExpectedOutcome:

    def test_diagnostics_driven_fixture_matches_expected_outcome(self):
        fixture = _load("diagnostics", "infeasible_diagnostics_driven_provisional.json")
        context = build_infeasibility_context(
            fixture["solver_status"], fixture["infeasibility_diagnostics"]
        )
        assert context.outcome == fixture["expected_outcome"]
        rendered = render_diagnostics_section(context)
        assert rendered == fixture["expected_rendered_output"]

    def test_status_only_fixture_renders_none_not_a_guess(self):
        fixture = _load("diagnostics", "infeasible_status_only_no_payload_real.json")
        context = build_infeasibility_context(
            fixture["solver_status"], fixture["infeasibility_diagnostics"]
        )
        assert context.outcome == fixture["expected_outcome"]
        rendered = render_diagnostics_section(context)
        assert rendered is fixture["expected_rendered_output"] is None


# ---------------------------------------------------------------------------
# Pack-level sanity: confirm the fixture counts match what Test_Pack_README.md
# documents, so the README can't silently drift from the actual folder.
# ---------------------------------------------------------------------------
def test_fixture_counts_match_documented_counts():
    assert len(_results_json_fixtures()) == 7
    assert len(_llm_reporting_fixtures()) == 4
    sensitivity_files = [
        f for f in os.listdir(os.path.join(_FIXTURES, "sensitivity"))
        if f.endswith(".json")
    ]
    assert len(sensitivity_files) == 1  # see Test_Pack_README.md "Known gaps"
    diagnostics_files = [
        f for f in os.listdir(os.path.join(_FIXTURES, "diagnostics"))
        if f.endswith(".json")
    ]
    assert len(diagnostics_files) == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
