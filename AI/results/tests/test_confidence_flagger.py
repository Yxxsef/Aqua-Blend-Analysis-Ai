import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from confidence_flagger import determine_confidence


def complete_provenance():
    return {
        "storage_capacity": "measured",
        "reference_flow": "measured",
        "max_available": "measured",
        "cost": "measured",
        "alkalinity": "measured",
    }


def estimated_provenance():
    return {
        "storage_capacity": "estimate",
        "reference_flow": "estimate",
        "max_available": "estimate",
        "cost": "estimate",
        "alkalinity": "estimate",
    }


def test_provisional_when_estimated_values_used():
    provenance_sources = [
        {
            "source_id": "groundwater_bore_1",
            "has_estimated_values": True,
            "provenance": estimated_provenance(),
        }
    ]

    selected_sources = [
        {
            "source_id": "groundwater_bore_1",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "PROVISIONAL"
    assert result["estimated_sources"] == [
        "groundwater_bore_1"
    ]


def test_measured_when_all_sources_confirmed():
    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False,
            "provenance": complete_provenance(),
        },
        {
            "source_id": "yarra_kew",
            "has_estimated_values": False,
            "provenance": complete_provenance(),
        },
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        },
        {
            "source_id": "yarra_kew",
        },
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "MEASURED"
    assert result["estimated_sources"] == []


def test_unknown_when_provenance_missing():
    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False,
        }
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "UNKNOWN"


def test_unknown_when_provenance_incomplete():
    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False,
            "provenance": {
                "storage_capacity": "measured",
                "reference_flow": "measured",
            },
        }
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "UNKNOWN"


def test_unknown_when_estimated_flag_is_not_boolean():
    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": "true",
            "provenance": complete_provenance(),
        }
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "UNKNOWN"


def test_unknown_when_estimated_flag_is_null():
    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": None,
            "provenance": complete_provenance(),
        }
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "UNKNOWN"


def test_unknown_when_source_id_missing():
    provenance_sources = [
        {
            "has_estimated_values": True,
            "provenance": estimated_provenance(),
        }
    ]

    selected_sources = [
        {
            "source_id": "groundwater_bore_1",
        }
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "UNKNOWN"
    assert result["estimated_sources"] == []


def test_unknown_when_source_list_empty():
    result = determine_confidence(
        [],
        [],
    )

    assert result["confidence"] == "UNKNOWN"
    assert result["estimated_sources"] == []


def test_mixed_estimated_and_missing_provenance():
    provenance_sources = [
        {
            "source_id": "groundwater_bore_1",
            "has_estimated_values": True,
            "provenance": estimated_provenance(),
        },
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False,
        },
    ]

    selected_sources = [
        {
            "source_id": "groundwater_bore_1",
        },
        {
            "source_id": "silvan_reservoir",
        },
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "PROVISIONAL"
    assert result["estimated_sources"] == [
        "groundwater_bore_1"
    ]


def test_unused_estimated_source_does_not_affect_confidence():
    """
    Regression test requested during review.

    The selected sources are fully measured.
    An unused source has estimated values.
    Confidence must remain MEASURED.
    """

    provenance_sources = [
        {
            "source_id": "silvan_reservoir",
            "has_estimated_values": False,
            "provenance": complete_provenance(),
        },
        {
            "source_id": "yarra_kew",
            "has_estimated_values": False,
            "provenance": complete_provenance(),
        },
        {
            "source_id": "groundwater_bore_1",
            "has_estimated_values": True,
            "provenance": estimated_provenance(),
        },
    ]

    selected_sources = [
        {
            "source_id": "silvan_reservoir",
        },
        {
            "source_id": "yarra_kew",
        },
    ]

    result = determine_confidence(
        provenance_sources,
        selected_sources,
    )

    assert result["confidence"] == "MEASURED"
    assert result["estimated_sources"] == []