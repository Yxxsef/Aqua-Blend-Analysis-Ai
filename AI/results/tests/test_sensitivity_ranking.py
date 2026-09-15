"""Task 90 regression tests for sensitivity_ranking.py."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, RESULTS_DIR)

from sensitivity_ranking import (  # noqa: E402
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_INPUT,
    rank_sensitivities,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "milp_model_output_example.json"
)

def _load_fixture() -> dict:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_current_milp_output_example_uses_top_level_sources() -> None:
    """The inspected current output should be accepted without data_flags."""
    fixture = _load_fixture()

    assert isinstance(fixture["sources"], list)
    assert fixture["sources"][0]["source_id"]
    assert "data_flags" not in fixture

    result = rank_sensitivities(fixture)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert result["verified_entries"] == []
    assert "provenance" in result["reason"].lower()
    assert "sensitivity" in result["reason"].lower()


def test_allow_estimated_values_is_not_used_as_source_provenance() -> None:
    """A policy allowing estimates is not proof that a source value is estimated."""
    fixture = _load_fixture()

    assert fixture["allow_estimated_values"] is True

    result = rank_sensitivities(fixture)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["verified_entries"] == []
    assert result["ranking"] == []


def test_current_source_records_do_not_expose_old_provenance_fields() -> None:
    fixture = _load_fixture()

    for source in fixture["sources"]:
        assert "has_estimated_values" not in source
        assert "provenance" not in source


def test_missing_top_level_sources_is_invalid_for_current_contract() -> None:
    result = rank_sensitivities({})

    assert result["status"] == STATUS_INVALID_INPUT
    assert "sources" in result["reason"].lower()


def test_malformed_source_id_is_invalid() -> None:
    fixture = _load_fixture()
    fixture["sources"][0]["source_id"] = ""

    result = rank_sensitivities(fixture)

    assert result["status"] == STATUS_INVALID_INPUT
    assert "source_id" in result["reason"]


def test_legacy_sensitivity_field_does_not_invent_missing_provenance() -> None:
    """Legacy sensitivity text alone is not enough to create a ranking."""
    fixture = copy.deepcopy(_load_fixture())
    fixture["sensitivity_to_key_assumptions"] = [
        {
            "assumption": "max_available_ml_per_day for SRC_002",
            "impact": "Lower availability may affect feasibility.",
        }
    ]

    result = rank_sensitivities(fixture)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert result["verified_entries"] == []
    assert "provenance" in result["reason"].lower()
