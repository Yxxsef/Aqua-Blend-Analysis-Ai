"""Task 61 integration tests for the Analysis & AI pipeline entry point."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import main
from model_runner import ModelConfig, rewrite_report


FIXTURE_PATH = (
    AI_DIR
    / "explanations"
    / "llm_reporting"
    / "fixtures"
    / "model_output_example.json"
)
PROTOTYPE_DISCLAIMER = "AquaBlend is a public-data decision-support proof-of-concept."


@pytest.fixture
def valid_results() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_optimal_result_uses_deterministic_fallback_without_model(
    valid_results: dict,
) -> None:
    original_results = copy.deepcopy(valid_results)

    response = main.run_pipeline(valid_results)

    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["solver_status"] == "OPTIMAL"
    assert response["kpis"]["demand_satisfaction"]["value"] == 100.0
    assert response["gate_result"] == "PASS"
    assert response["confidence_flag"] == "PROVISIONAL"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert PROTOTYPE_DISCLAIMER in response["display_explanation"]
    assert valid_results == original_results


def test_incomplete_dictionary_returns_invalid_input() -> None:
    response = main.run_pipeline({"scenario_id": "partial-scenario"})

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] == "partial-scenario"
    assert response["solver_status"] is None
    assert response["kpis"] is None
    assert any("Missing required fields" in warning for warning in response["warnings"])


def test_non_object_input_returns_invalid_input() -> None:
    response = main.run_pipeline(["not", "a", "JSON object"])

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] is None
    assert any("Results must be a JSON object" in warning for warning in response["warnings"])


def test_unsupported_feasible_status_returns_invalid_input(valid_results: dict) -> None:
    results = copy.deepcopy(valid_results)
    results["status"] = "FEASIBLE"

    response = main.run_pipeline(results)

    assert response["report_mode"] == "INVALID_INPUT"
    assert any("not supported by the App response contract" in warning for warning in response["warnings"])


def test_unbounded_result_returns_status_only_response(valid_results: dict) -> None:
    results = copy.deepcopy(valid_results)
    results["status"] = "UNBOUNDED"

    response = main.run_pipeline(results)

    assert response["solver_status"] == "UNBOUNDED"
    assert response["report_mode"] == "STATUS_ONLY"
    assert response["kpis"] is None
    assert response["comparison"] is None
    assert response["report_mode"] != "INVALID_INPUT"


def test_accepted_llm_rewrite_is_displayed(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_request(_url, _headers, payload, _timeout_seconds):
        prompt = payload["messages"][1]["content"]
        report = prompt.split("<deterministic_report>\n", 1)[1].rsplit(
            "\n</deterministic_report>", 1
        )[0]
        return {"choices": [{"message": {"content": report}}]}

    def rewrite_with_fake_request(deterministic_report, config):
        return rewrite_report(
            deterministic_report,
            config,
            request_fn=fake_request,
        )

    monkeypatch.setattr(main, "rewrite_report", rewrite_with_fake_request)

    response = main.run_pipeline(
        valid_results,
        model_config=ModelConfig(model_id="test-model"),
    )

    assert response["report_mode"] == "LLM_VALIDATED"


def test_rejected_llm_rewrite_uses_deterministic_fallback(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_request(*_args, **_kwargs):
        return {
            "choices": [
                {"message": {"content": "The result is completely safe and costs $1."}}
            ]
        }

    def rewrite_with_fake_request(deterministic_report, config):
        return rewrite_report(
            deterministic_report,
            config,
            request_fn=fake_request,
        )

    monkeypatch.setattr(main, "rewrite_report", rewrite_with_fake_request)

    response = main.run_pipeline(
        valid_results,
        model_config=ModelConfig(model_id="test-model"),
    )

    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert PROTOTYPE_DISCLAIMER in response["display_explanation"]
    assert any("LLM rewrite was rejected by validation" in warning for warning in response["warnings"])


# Task 61 follow-up: integration from MILP output to AI


class _FakeExecuteResult:
    def __init__(self, data: object) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, row: object, calls: list) -> None:
        self._row = row
        self._calls = calls

    def select(self, columns: str) -> _FakeQuery:
        self._calls.append(("select", columns))
        return self

    def order(self, column: str, desc: bool) -> _FakeQuery:
        self._calls.append(("order", column, desc))
        return self

    def limit(self, count: int) -> _FakeQuery:
        self._calls.append(("limit", count))
        return self

    def single(self) -> _FakeQuery:
        self._calls.append(("single",))
        return self

    def execute(self) -> _FakeExecuteResult:
        self._calls.append(("execute",))
        return _FakeExecuteResult(self._row)


class _FakeSupabaseClient:
    def __init__(self, row: object, calls: list) -> None:
        self._row = row
        self._calls = calls

    def table(self, name: str) -> _FakeQuery:
        self._calls.append(("table", name))
        return _FakeQuery(self._row, self._calls)


def _install_fake_supabase(monkeypatch: pytest.MonkeyPatch, row: object) -> list:
    calls: list = []

    def fake_create_client(**kwargs: object) -> _FakeSupabaseClient:
        calls.append(("create_client", kwargs))
        return _FakeSupabaseClient(row, calls)

    monkeypatch.setattr(main, "create_client", fake_create_client)
    return calls


def test_load_milp_output_reads_the_latest_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_supabase(monkeypatch, {"scenario_id": "row-from-db"})

    output = main.load_milp_output("ignored.json")

    assert output == {"scenario_id": "row-from-db"}
    assert ("table", "milp_model_output") in calls
    assert ("select", "*") in calls
    assert ("order", "run_id", True) in calls
    assert ("limit", 1) in calls
    assert ("single",) in calls


def test_load_milp_output_ignores_its_path_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_supabase(monkeypatch, {"scenario_id": "same-row"})

    from_fixture = main.load_milp_output(FIXTURE_PATH)
    from_missing_path = main.load_milp_output("/nonexistent/path.json")

    assert from_fixture == from_missing_path == {"scenario_id": "same-row"}
    assert [call for call in calls if call[0] == "table"] == [
        ("table", "milp_model_output"),
        ("table", "milp_model_output"),
    ]


def test_run_from_file_runs_the_pipeline_on_the_supabase_row(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, valid_results)

    response = main.run_from_file("ignored.json")

    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["solver_status"] == "OPTIMAL"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"


def test_run_from_file_rejects_a_row_that_is_not_results_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, {"run_id": 7, "scenario_id": "db-row"})

    response = main.run_from_file("ignored.json")

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] == "db-row"
    assert any("Missing required fields" in warning for warning in response["warnings"])


def test_run_from_file_handles_an_empty_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, None)

    response = main.run_from_file("ignored.json")

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] is None
    assert any("Results must be a JSON object" in warning for warning in response["warnings"])
