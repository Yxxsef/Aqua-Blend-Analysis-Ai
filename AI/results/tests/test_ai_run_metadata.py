from AI.results.ai_run_metadata import AIRunMetadata, build_ai_run_metadata


def test_build_full_ai_run_metadata():
    metadata = build_ai_run_metadata(
        scenario_id="scenario_001",
        run_id="run_001",
        model_id="test-model",
        prompt_version="prompt-v1",
        runtime_ms=1250,
        validator_result="PASS",
        fallback_used=False,
        fallback_reason=None,
        confidence="HIGH",
    )

    assert isinstance(metadata, AIRunMetadata)
    assert metadata.scenario_id == "scenario_001"
    assert metadata.run_id == "run_001"
    assert metadata.model_id == "test-model"
    assert metadata.prompt_version == "prompt-v1"
    assert metadata.runtime_ms == 1250
    assert metadata.validator_result == "PASS"
    assert metadata.fallback_used is False
    assert metadata.fallback_reason is None
    assert metadata.confidence == "HIGH"
    assert metadata.module_version == "task-73-v1"


def test_missing_optional_values_remain_none():
    metadata = build_ai_run_metadata()

    assert metadata.scenario_id is None
    assert metadata.run_id is None
    assert metadata.model_id is None
    assert metadata.prompt_version is None
    assert metadata.runtime_ms is None
    assert metadata.validator_result is None
    assert metadata.fallback_used is None
    assert metadata.fallback_reason is None
    assert metadata.confidence is None


def test_supplied_ids_are_preserved():
    metadata = build_ai_run_metadata(
        scenario_id="scenario_backend_123",
        run_id="run_backend_456",
    )

    assert metadata.scenario_id == "scenario_backend_123"
    assert metadata.run_id == "run_backend_456"


def test_fallback_metadata_is_recorded():
    metadata = build_ai_run_metadata(
        model_id="test-model",
        runtime_ms=30000,
        fallback_used=True,
        fallback_reason="TIMEOUT",
    )

    assert metadata.fallback_used is True
    assert metadata.fallback_reason == "TIMEOUT"
    assert metadata.runtime_ms == 30000


def test_to_dict_returns_machine_readable_metadata():
    metadata = build_ai_run_metadata(
        scenario_id="scenario_001",
        run_id="run_001",
        validator_result="PASS",
    )

    result = metadata.to_dict()

    assert isinstance(result, dict)
    assert result["scenario_id"] == "scenario_001"
    assert result["run_id"] == "run_001"
    assert result["validator_result"] == "PASS"
    assert result["module_version"] == "task-73-v1"
