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
from postgrest.exceptions import APIError

from prompts import PROMPT_VERSION


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
    def __init__(self, rows: object, calls: list) -> None:
        self._rows = rows
        self._calls = calls

    def select(self, columns: str) -> _FakeQuery:
        self._calls.append(("select", columns))
        return self

    def order(self, column: str, desc: bool) -> _FakeQuery:
        self._calls.append(("order", column, desc))
        return self

    def eq(self, column: str, value: object) -> _FakeQuery:
        self._calls.append(("eq", column, value))
        self._rows = [
            row for row in self._rows
            if isinstance(row, dict) and row.get(column) == value
        ]
        return self

    def limit(self, count: int) -> _FakeQuery:
        self._calls.append(("limit", count))
        return self

    def insert(self, row: dict) -> _FakeQuery:
        self._calls.append(("insert", row))
        self._rows = [row]
        return self

    def execute(self) -> _FakeExecuteResult:
        self._calls.append(("execute",))
        return _FakeExecuteResult(self._rows)


class _FakeSupabaseClient:
    def __init__(self, rows: object, calls: list, fail_on: str | None) -> None:
        self._rows = rows
        self._calls = calls
        self._fail_on = fail_on

    def table(self, name: str) -> _FakeQuery:
        self._calls.append(("table", name))
        if self._fail_on == name:
            raise APIError({"message": f"{name} is unavailable", "code": "08006"})
        return _FakeQuery(self._rows, self._calls)


def _install_fake_supabase(
    monkeypatch: pytest.MonkeyPatch,
    row: object,
    fail_on: str | None = None,
) -> list:
    """Patch main.create_client with a fake.

    ``row`` is the single milp_model_output row a read returns; None means an
    empty table. ``fail_on`` names a table whose access raises, standing in for
    a connection or permission failure.
    """
    calls: list = []
    rows = [] if row is None else [row]

    def fake_create_client(**kwargs: object) -> _FakeSupabaseClient:
        calls.append(("create_client", kwargs))
        return _FakeSupabaseClient(rows, calls, fail_on)

    monkeypatch.setattr(main, "create_client", fake_create_client)
    return calls


def test_load_milp_output_reads_the_latest_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_supabase(monkeypatch, {"scenario_id": "row-from-db"})

    output = main.load_milp_output()

    assert output == {"scenario_id": "row-from-db"}
    assert ("table", "milp_model_output") in calls
    assert ("select", "*") in calls
    assert ("order", "created_at", True) in calls
    assert ("limit", 1) in calls


def test_run_from_source_runs_the_pipeline_on_the_supabase_row(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, valid_results)

    response = main.run_from_source()

    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["solver_status"] == "OPTIMAL"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"


def test_run_from_source_rejects_a_row_that_is_not_results_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, {"origin_run_id": 7, "scenario_id": "db-row"})

    response = main.run_from_source()

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] == "db-row"
    assert any("Missing required fields" in warning for warning in response["warnings"])


def test_run_from_source_handles_an_empty_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, None)

    response = main.run_from_source()

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["scenario_id"] is None
    assert any("contains no rows to analyse" in warning for warning in response["warnings"])


@pytest.fixture
def milp_row(valid_results: dict) -> dict:
    """A milp_model_output row: the Results JSON plus its database columns."""
    return {
        **valid_results,
        "id": "6f1d2c3b-0000-4000-8000-000000000001",
        "scenario_db_id": 42,
        "origin_run_id": 7,
    }


def test_save_ai_output_reads_foreign_keys_from_the_milp_row(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)
    db_row = {
        "id": "6f1d2c3b-0000-4000-8000-000000000001",
        "scenario_db_id": 42,
        "origin_run_id": 7,
    }

    main.save_ai_output(response, db_row)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert ("table", "milp_ai_output") in calls
    assert row["milp_output_id"] == "6f1d2c3b-0000-4000-8000-000000000001"
    assert row["scenario_id"] == 42
    assert row["origin_run_id"] == 7
    assert row["milp_output_hash"] == main._sha256_json(db_row)
    assert row["ai_output_hash"] == main._sha256_json(response)
    assert row["ai_contract_version"] == response["contract_version"]
    assert row["raw_ai_json"] == response
    assert row["warnings"] == response["warnings"]


def test_save_ai_output_rejects_a_row_without_foreign_keys(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)

    with pytest.raises(main.SupabaseError, match="milp_ai_output"):
        main.save_ai_output(response, {"origin_run_id": 7})


def test_save_ai_output_records_the_model_only_when_one_ran(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)
    db_row = {"id": "row-id", "scenario_db_id": 42}

    main.save_ai_output(response, db_row)
    main.save_ai_output(response, db_row, model_config=ModelConfig(model_id="test-model"))

    without_model, with_model = [call[1] for call in calls if call[0] == "insert"]
    assert "ai_model" not in without_model
    assert with_model["ai_model"] == "test-model"
    assert with_model["prompt_version"] == PROMPT_VERSION


def test_run_from_source_pushes_the_response_when_requested(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    response = main.run_from_source(push=True)

    inserts = [call for call in calls if call[0] == "insert"]
    assert len(inserts) == 1
    row = inserts[0][1]
    assert ("table", "milp_ai_output") in calls
    assert row["milp_output_id"] == milp_row["id"]
    assert row["origin_run_id"] == 7
    assert row["status"] == "completed"
    assert row["raw_ai_json"] == response
    assert row["decision_explanation"] == response["display_explanation"]
    assert row["latency_ms"] >= 0


def test_run_from_source_does_not_push_by_default(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.run_from_source()

    assert [call for call in calls if call[0] == "insert"] == []
    assert ("table", "milp_ai_output") not in calls


def test_push_records_an_invalid_input_response_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_supabase(
        monkeypatch, {"id": "row-id", "scenario_db_id": 42, "origin_run_id": 7}
    )

    response = main.run_from_source(push=True)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert response["report_mode"] == "INVALID_INPUT"
    assert row["status"] == "failed"
    assert row["scenario_id"] == 42


def test_load_milp_output_wraps_a_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, None, fail_on="milp_model_output")

    with pytest.raises(main.SupabaseError, match="milp_model_output"):
        main.load_milp_output()


def test_load_milp_output_reports_an_empty_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, None)

    with pytest.raises(main.SupabaseError, match="no rows to analyse"):
        main.load_milp_output()


def test_unreachable_database_becomes_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_supabase(monkeypatch, None, fail_on="milp_model_output")

    response = main.run_from_source()

    assert response["report_mode"] == "INVALID_INPUT"
    assert response["solver_status"] is None
    assert any("Supabase read failed" in warning for warning in response["warnings"])


def test_failed_push_keeps_the_response_and_warns(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, milp_row, fail_on="milp_ai_output")

    response = main.run_from_source(push=True)

    # The analysis still succeeded; only the write failed.
    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert any(
        warning.startswith(main.PUSH_FAILURE_PREFIX)
        for warning in response["warnings"]
    )


def test_a_successful_push_adds_no_failure_warning(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, milp_row)

    response = main.run_from_source(push=True)

    assert not any(
        warning.startswith(main.PUSH_FAILURE_PREFIX)
        for warning in response["warnings"]
    )


def test_push_uses_the_milp_published_output_hash(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)
    db_row = {"id": "row-id", "scenario_db_id": 42, "output_hash": "milp-published"}

    main.save_ai_output(response, db_row)

    row = [call for call in calls if call[0] == "insert"][0][1]
    # MILP's own digest, not one we recompute: both tables index on it.
    assert row["milp_output_hash"] == "milp-published"


def test_push_falls_back_to_a_computed_hash(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)
    db_row = {"id": "row-id", "scenario_db_id": 42}  # output_hash is nullable

    main.save_ai_output(response, db_row)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert row["milp_output_hash"] == main._sha256_json(db_row)


def test_a_failed_analysis_fills_the_error_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_supabase(
        monkeypatch, {"id": "row-id", "scenario_db_id": 42, "origin_run_id": 7}
    )

    response = main.run_from_source(push=True)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert response["report_mode"] == "INVALID_INPUT"
    assert row["status"] == "failed"
    assert row["error_code"] == "INVALID_INPUT"
    assert "Results validation failed" in row["error_message"]


def test_a_successful_analysis_leaves_the_error_columns_unset(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.run_from_source(push=True)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert row["status"] == "completed"
    assert "error_code" not in row
    assert "error_message" not in row


def test_push_records_when_the_run_started(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.run_from_source(push=True)

    row = [call for call in calls if call[0] == "insert"][0][1]
    assert row["started_at"] <= row["completed_at"]


def test_a_row_without_scenario_db_id_is_a_supabase_error(
    valid_results: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # scenario_db_id is nullable upstream but NOT NULL in milp_ai_output, so
    # this must report cleanly rather than escape run_from_file's handler.
    _install_fake_supabase(monkeypatch, None)
    response = main.run_pipeline(valid_results)

    with pytest.raises(main.SupabaseError, match="scenario_db_id"):
        main.save_ai_output(response, {"id": "row-id", "scenario_db_id": None})


def test_a_file_path_bypasses_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_supabase(monkeypatch, None)

    response = main.run_from_source(FIXTURE_PATH)

    assert response["scenario_id"] == "scenario_2026_07_17_001"
    assert response["report_mode"] == "TEMPLATE_FALLBACK"
    assert calls == []  # the database was never touched


def test_an_unreadable_file_returns_invalid_input(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"

    response = main.run_from_source(missing)

    assert response["report_mode"] == "INVALID_INPUT"
    assert any("file could not be read" in warning for warning in response["warnings"])


def test_malformed_json_returns_invalid_input(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    response = main.run_from_source(broken)

    assert response["report_mode"] == "INVALID_INPUT"
    assert any("file could not be read" in warning for warning in response["warnings"])


def test_run_id_filters_on_origin_run_id(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.load_milp_output(run_id=7)

    assert ("eq", "origin_run_id", 7) in calls


def test_scenario_db_id_filters_on_that_column(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.load_milp_output(scenario_db_id=42)

    assert ("eq", "scenario_db_id", 42) in calls


def test_scenario_filters_on_the_display_string(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.load_milp_output(scenario="scenario_2026_07_17_001")

    assert ("eq", "scenario_id", "scenario_2026_07_17_001") in calls


def test_no_selector_keeps_the_newest_row_ordering(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_supabase(monkeypatch, milp_row)

    main.load_milp_output()

    assert ("order", "created_at", True) in calls
    assert not [call for call in calls if call[0] == "eq"]


def test_an_unmatched_selector_names_what_was_asked_for(
    milp_row: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_supabase(monkeypatch, milp_row)

    with pytest.raises(main.SupabaseError, match="origin_run_id=999"):
        main.load_milp_output(run_id=999)
