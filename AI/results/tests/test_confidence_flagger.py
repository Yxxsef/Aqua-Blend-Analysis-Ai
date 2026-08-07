import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from confidence_flagger import determine_confidence


def test_provisional_when_estimated_values_used():

    sources = [
        {
            "source_id": "groundwater_bore_1",
            "has_estimated_values": True
        }
    ]

    result = determine_confidence(sources)

    assert result["confidence"] == "PROVISIONAL"
    assert "groundwater_bore_1" in result["estimated_sources"]



def test_measured_when_all_sources_confirmed():

    sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False
        },
        {
            "source_id": "yarra_kew",
            "has_estimated_values": False
        }
    ]

    result = determine_confidence(sources)

    assert result["confidence"] == "MEASURED"
    assert result["estimated_sources"] == []



def test_unknown_when_provenance_missing():

    sources = [
        {
            "source_id": "silvan_reservoir"
        }
    ]

    result = determine_confidence(sources)

    assert result["confidence"] == "UNKNOWN"