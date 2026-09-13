import json
import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.dirname(CURRENT_DIR)

sys.path.insert(0, RESULTS_DIR)

from sensitivity_ranking import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_INPUT,
    rank_sensitivities,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "fixtures"
    / "milp_v1_solved_example.json"
)

def _load_fixture() -> dict:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_latest_available_solved_fixture_uses_top_level_sources() -> None:
    """The solved v1 fixture must no longer fail because data_flags is absent."""
    result = rank_sensitivities(_load_fixture())

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert result["verified_entries"] == []
    assert "sensitivity" in result["reason"].lower()


def test_missing_top_level_sources_is_invalid_for_current_contract() -> None:
    result = rank_sensitivities({})

    assert result["status"] == STATUS_INVALID_INPUT
    assert "sources" in result["reason"]


def test_unconfirmed_source_provenance_returns_insufficient_data() -> None:
    result = rank_sensitivities(
        {
            "sources": [
                {
                    "source_id": "yarra_kew",
                    "activated": True,
                    "withdrawal_ml_per_day": 290.0,
                    "selection_status": "SELECTED",
                }
            ],
            "sensitivity_to_key_assumptions": [
                {
                    "assumption": (
                        "max_available_ml_per_day for yarra_kew"
                    ),
                    "impact": "Lower availability may affect feasibility.",
                }
            ],
        }
    )

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["verified_entries"] == []
    assert "provenance" in result["reason"].lower()


def test_confirmed_estimated_provenance_is_verified_without_inventing_rank() -> None:
    """Existing provenance names are used only when they are actually supplied."""
    result = rank_sensitivities(
        {
            "sources": [
                {
                    "source_id": "yarra_kew",
                    "has_estimated_values": True,
                    "provenance": {
                        "max_available": "estimate",
                    },
                }
            ],
            "sensitivity_to_key_assumptions": [
                {
                    "assumption": (
                        "max_available_ml_per_day for yarra_kew"
                    ),
                    "impact": "Lower availability may affect feasibility.",
                }
            ],
        }
    )

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["ranking"] == []
    assert result["verified_entries"] == [
        {
            "assumption": "max_available_ml_per_day for yarra_kew",
            "impact": "Lower availability may affect feasibility.",
            "source_id": "yarra_kew",
            "provenance_field": "max_available",
        }
    ]
