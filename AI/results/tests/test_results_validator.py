import sys
import os
import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from results_validator import (
    validate_results,
    ValidationError
)


def valid_results():
    return {
        "scenario": {
            "name": "normal"
        },
        "status": "SUCCESS",
        "sources": [
            {
                "source_id": "silvan_reservoir"
            }
        ],
        "demand": {
            "required_volume_ML": 500
        },
        "cost": {
            "total_AUD": 1000
        },
        "constraints": {},
        "quality_stage": {
            "stage": "final"
        },
        "diagnostics": {}
    }


def test_valid_results_pass():
    results = valid_results()

    assert validate_results(results) is True


def test_missing_required_field():
    results = valid_results()

    del results["cost"]

    with pytest.raises(ValidationError):
        validate_results(results)


def test_invalid_sources_type():
    results = valid_results()

    results["sources"] = "silvan"

    with pytest.raises(ValidationError):
        validate_results(results)