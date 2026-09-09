"""
test_diagnostics_adapter.py

AquaBlend | Analysis & AI | Sprint 3 | Task 71
Tests for diagnostics_adapter.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnostics_adapter import (  # noqa: E402
    DiagnosticCause,
    DiagnosticsAdapterError,
    InfeasibilityContext,
    OUTCOME_INFEASIBLE_STATUS_ONLY,
    OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS,
    OUTCOME_OPTIMAL,
    OUTCOME_TECHNICAL_FAILURE,
    build_infeasibility_context,
    render_diagnostics_section,
)

# The integration architecture doc's own "conceptual diagnostic result"
# example (section 20), used verbatim so these tests are checked against
# the actual real-world shape this module was designed around, not a
# convenient stand-in.
INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS = {
    "likely_causes": [
        {
            "type": "insufficient_source_supply",
            "severity": "high",
            "details": "Available source capacity is below total required demand.",
        },
        {
            "type": "plant_capacity_limit",
            "severity": "medium",
            "plant_id": "plant_01",
        },
    ]
}


class TestOptimalAndFeasibleStatuses:
    """Statuses this module was never asked to classify as infeasibility-
    shaped must still resolve safely, not crash."""

    def test_optimal_gets_its_own_outcome_not_technical_failure(self):
        """Regression test for a real PR review finding (Task 71,
        Yousef): OPTIMAL must never be classified the same way as a
        genuine solver crash. An earlier version of this function only
        checked "is this infeasibility-shaped", so a successful solve
        fell through to TECHNICAL_FAILURE simply because OPTIMAL is
        neither INFEASIBLE nor UNBOUNDED - correct in the narrow sense,
        actively misleading in the result it produced."""
        ctx = build_infeasibility_context("OPTIMAL")
        assert ctx.outcome == OUTCOME_OPTIMAL
        assert ctx.outcome != OUTCOME_TECHNICAL_FAILURE

    def test_optimal_renders_none_not_a_technical_failure_message(self):
        """A successful solve must not produce a "this is a technical
        failure" message - render_diagnostics_section() must correctly
        have nothing to say for a genuinely successful run."""
        ctx = build_infeasibility_context("OPTIMAL")
        assert render_diagnostics_section(ctx) is None

    def test_time_limit_is_technical_failure_bucket(self):
        """TIME_LIMIT is not a proof of infeasibility either - Results_
        JSON_Field_Map.md says not to assume it's usable at all, so it
        must not be treated as a mathematical infeasibility result."""
        ctx = build_infeasibility_context("TIME_LIMIT")
        assert ctx.outcome == OUTCOME_TECHNICAL_FAILURE

    def test_completely_unrecognised_status_is_technical_failure_bucket(self):
        """A status this module has never heard of must degrade safely,
        not raise - defensive coverage for a future status value."""
        ctx = build_infeasibility_context("SOME_FUTURE_STATUS")
        assert ctx.outcome == OUTCOME_TECHNICAL_FAILURE


class TestErrorStatus:
    """ERROR is the explicit technical-failure case this module exists to
    keep separate from a genuine mathematical infeasibility finding."""

    def test_error_status_is_technical_failure(self):
        ctx = build_infeasibility_context("ERROR")
        assert ctx.outcome == OUTCOME_TECHNICAL_FAILURE
        assert ctx.causes == ()

    def test_error_status_with_diagnostics_payload_still_technical_failure(self):
        """Even if a diagnostics payload is accidentally supplied
        alongside ERROR, it must not be used - ERROR means the solver
        didn't reach a real mathematical conclusion, so there is nothing
        genuine to diagnose."""
        ctx = build_infeasibility_context("ERROR", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS)
        assert ctx.outcome == OUTCOME_TECHNICAL_FAILURE
        assert ctx.causes == ()

    def test_error_renders_a_safe_distinguishing_message(self):
        ctx = build_infeasibility_context("ERROR")
        text = render_diagnostics_section(ctx)
        assert text is not None
        assert "technical failure" in text.lower()
        assert "not a mathematical proof" in text.lower()


class TestInfeasibleWithoutDiagnostics:
    """The core safety case: INFEASIBLE with nothing supplied must never
    let anything downstream invent a cause."""

    def test_infeasible_with_no_diagnostics_argument_is_status_only(self):
        ctx = build_infeasibility_context("INFEASIBLE")
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY
        assert ctx.causes == ()

    def test_infeasible_with_explicit_none_is_status_only(self):
        ctx = build_infeasibility_context("INFEASIBLE", None)
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_infeasible_with_empty_dict_is_status_only(self):
        ctx = build_infeasibility_context("INFEASIBLE", {})
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_infeasible_with_empty_causes_list_is_status_only(self):
        ctx = build_infeasibility_context("INFEASIBLE", {"likely_causes": []})
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_status_only_renders_none_not_a_guessed_explanation(self):
        """The specific behaviour the whole task exists to guarantee: no
        text is ever produced for a status-only infeasible result. A
        caller must see None and correctly do nothing with it, not
        receive an empty string or a generic filler sentence that could
        be mistaken for a real explanation."""
        ctx = build_infeasibility_context("INFEASIBLE")
        assert render_diagnostics_section(ctx) is None


class TestInfeasibleWithGenuineDiagnostics:
    """The real integration-doc example, checked field by field."""

    def test_the_integration_doc_example_is_classified_correctly(self):
        ctx = build_infeasibility_context(
            "INFEASIBLE", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS
        )
        assert ctx.outcome == OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS
        assert ctx.has_causes()
        assert len(ctx.causes) == 2

    def test_first_cause_fields_are_parsed_correctly(self):
        ctx = build_infeasibility_context(
            "INFEASIBLE", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS
        )
        first = ctx.causes[0]
        assert first.cause_type == "insufficient_source_supply"
        assert first.severity == "high"
        assert first.details == "Available source capacity is below total required demand."
        assert first.affected_ids == {}

    def test_second_cause_affected_id_is_captured_generically(self):
        """plant_id isn't a named field on DiagnosticCause - it must be
        captured through the generic affected_ids mechanism, proving the
        design survives an ID field name this module doesn't hard-code."""
        ctx = build_infeasibility_context(
            "INFEASIBLE", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS
        )
        second = ctx.causes[1]
        assert second.cause_type == "plant_capacity_limit"
        assert second.severity == "medium"
        assert second.details is None
        assert second.affected_ids == {"plant_id": "plant_01"}

    def test_a_different_id_field_name_is_also_captured(self):
        """The real contract might use source_id, zone_id, link_id, or
        something else entirely - none of these should need a code
        change here."""
        payload = {
            "likely_causes": [
                {"type": "demand_exceeds_capacity", "severity": "high", "zone_id": "zone_1", "link_id": "link_7"},
            ]
        }
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.causes[0].affected_ids == {"zone_id": "zone_1", "link_id": "link_7"}

    def test_rendered_text_traces_every_word_to_a_supplied_field(self):
        """Nothing in the rendered text may be invented - every cause
        type, severity, detail, and ID must come directly from the
        supplied payload."""
        ctx = build_infeasibility_context(
            "INFEASIBLE", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS
        )
        text = render_diagnostics_section(ctx)
        assert "insufficient_source_supply" in text
        assert "high" in text
        assert "Available source capacity is below total required demand." in text
        assert "plant_capacity_limit" in text
        assert "medium" in text
        assert "plant_01" in text


class TestUnbounded:
    """UNBOUNDED is explicitly out of this task's primary scope - always
    status-only, even with a diagnostics payload supplied, until that
    assumption is confirmed. See the module docstring."""

    def test_unbounded_with_no_diagnostics_is_status_only(self):
        ctx = build_infeasibility_context("UNBOUNDED")
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_unbounded_with_a_diagnostics_payload_is_still_status_only(self):
        """The deliberate, documented scope limitation: even genuine-
        looking diagnostics for UNBOUNDED must not be used yet."""
        ctx = build_infeasibility_context("UNBOUNDED", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS)
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY
        assert ctx.causes == ()

    def test_unbounded_status_only_also_renders_none(self):
        ctx = build_infeasibility_context("UNBOUNDED", INTEGRATION_DOC_EXAMPLE_DIAGNOSTICS)
        assert render_diagnostics_section(ctx) is None


class TestMalformedDiagnosticsDegradeSafely:
    """Every case here must degrade to status-only, never raise - see the
    module docstring's "Malformed input handling" section."""

    def test_diagnostics_is_a_plain_string_not_a_mapping(self):
        ctx = build_infeasibility_context("INFEASIBLE", "not a real payload")
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_diagnostics_is_a_list_not_a_mapping(self):
        ctx = build_infeasibility_context("INFEASIBLE", ["insufficient_source_supply"])
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_likely_causes_is_missing_entirely(self):
        ctx = build_infeasibility_context("INFEASIBLE", {"some_other_key": "value"})
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_likely_causes_is_a_string_not_a_list(self):
        ctx = build_infeasibility_context("INFEASIBLE", {"likely_causes": "oops"})
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_a_cause_entry_that_is_not_a_mapping_is_skipped(self):
        payload = {"likely_causes": ["just a string", {"type": "real_cause"}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.outcome == OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS
        assert len(ctx.causes) == 1
        assert ctx.causes[0].cause_type == "real_cause"

    def test_a_cause_entry_missing_type_is_skipped_not_fatal(self):
        """type is the one truly required field on a cause entry - an
        entry missing it is dropped, but must not take down the other,
        well-formed causes in the same payload."""
        payload = {
            "likely_causes": [
                {"severity": "high", "details": "no type given"},
                {"type": "well_formed_cause", "severity": "low"},
            ]
        }
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.outcome == OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS
        assert len(ctx.causes) == 1
        assert ctx.causes[0].cause_type == "well_formed_cause"

    def test_a_cause_entry_with_empty_string_type_is_skipped(self):
        payload = {"likely_causes": [{"type": "   "}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY

    def test_all_causes_malformed_falls_back_to_status_only(self):
        """If every entry in likely_causes is unusable, the overall
        outcome must correctly fall back to status-only, not report an
        empty INFEASIBLE_WITH_DIAGNOSTICS state."""
        payload = {"likely_causes": [{"severity": "high"}, {"details": "still no type"}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY
        assert ctx.causes == ()

    def test_missing_severity_defaults_safely_not_invented(self):
        payload = {"likely_causes": [{"type": "some_cause"}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.causes[0].severity == "unspecified"

    def test_non_string_severity_falls_back_to_default(self):
        payload = {"likely_causes": [{"type": "some_cause", "severity": 5}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.causes[0].severity == "unspecified"

    def test_non_string_details_is_dropped_not_stringified(self):
        """A malformed details field (e.g. a dict where a string was
        expected) must not be silently coerced into text - that could
        inject something unintended into the rendered report."""
        payload = {"likely_causes": [{"type": "some_cause", "details": {"nested": "object"}}]}
        ctx = build_infeasibility_context("INFEASIBLE", payload)
        assert ctx.causes[0].details is None


class TestSolverStatusValidation:
    """The one case this module DOES raise on - a genuine caller error,
    not a data-quality gap."""

    def test_empty_string_status_raises(self):
        with pytest.raises(DiagnosticsAdapterError):
            build_infeasibility_context("")

    def test_whitespace_only_status_raises(self):
        with pytest.raises(DiagnosticsAdapterError):
            build_infeasibility_context("   ")

    def test_none_status_raises(self):
        with pytest.raises(DiagnosticsAdapterError):
            build_infeasibility_context(None)  # type: ignore[arg-type]


class TestSolverMetadataDiagnosticsCollisionIsHarmless:
    """Directly tests the naming-collision warning in the module
    docstring: passing the EXISTING diagnostics.* solver-metadata object
    (Results_JSON_Field_Map.md) by mistake, instead of the real
    infeasibility-cause payload, must fail safely to status-only, not
    crash and not silently fabricate causes from unrelated fields."""

    def test_solver_metadata_object_produces_no_causes(self):
        solver_metadata = {
            "solver": "HiGHS",
            "solve_time_seconds": 1.4,
            "optimality_gap": 0.0,
            "num_continuous_variables": 12,
            "num_binary_variables": 4,
            "num_integer_variables": 0,
            "num_constraints": 20,
        }
        ctx = build_infeasibility_context("INFEASIBLE", solver_metadata)
        assert ctx.outcome == OUTCOME_INFEASIBLE_STATUS_ONLY
        assert ctx.causes == ()


class TestInfeasibilityContextShape:
    """Basic shape/dataclass contract tests."""

    def test_has_causes_false_when_empty(self):
        ctx = InfeasibilityContext(outcome=OUTCOME_INFEASIBLE_STATUS_ONLY, solver_status="INFEASIBLE")
        assert ctx.has_causes() is False

    def test_has_causes_true_when_populated(self):
        cause = DiagnosticCause(cause_type="x")
        ctx = InfeasibilityContext(
            outcome=OUTCOME_INFEASIBLE_WITH_DIAGNOSTICS,
            solver_status="INFEASIBLE",
            causes=(cause,),
        )
        assert ctx.has_causes() is True

    def test_diagnostic_cause_default_severity_is_unspecified(self):
        cause = DiagnosticCause(cause_type="x")
        assert cause.severity == "unspecified"

    def test_diagnostic_cause_default_affected_ids_is_empty_dict(self):
        cause = DiagnosticCause(cause_type="x")
        assert cause.affected_ids == {}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
