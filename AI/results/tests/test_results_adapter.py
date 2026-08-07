import sys
import os
import pytest

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from results_adapter import (
    adapt_results,
    AdapterError
)


def sample_results():

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



def test_adapter_converts_fields():

    result = adapt_results(sample_results())

    assert result["scenario"]["name"] == "normal"
    assert result["qualityStage"]["stage"] == "final"



def test_adapter_missing_field():

    results = sample_results()

    del results["status"]

    with pytest.raises(AdapterError):

        adapt_results(results)



def test_adapter_requires_dictionary():

    with pytest.raises(AdapterError):

        adapt_results([])