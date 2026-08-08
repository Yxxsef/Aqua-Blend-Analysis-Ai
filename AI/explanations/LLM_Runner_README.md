# AquaBlend LLM Report Runner

## Purpose

This component sends an already-generated deterministic AquaBlend report to a small instruction model for a controlled wording rewrite.

The runner does **not** read raw Results JSON, calculate values, choose sources, judge water safety, or replace the deterministic report. A successful model response is labelled `LLM_UNVALIDATED` until the Task 25 validator accepts it.

## Flow

```text
Validated Results JSON
-> deterministic fallback report
-> prompts.py
-> OpenAI-compatible local model endpoint
-> LLM_UNVALIDATED rewrite
-> Task 25 factual and safety validation
-> validated LLM report or TEMPLATE_FALLBACK
```

## Files

- `prompts.py`: prompt version and strict rewrite instructions.
- `model_runner.py`: configuration loading, model call, metadata, and safe fallback.
- `model_config.example.json`: example local endpoint configuration.
- `tests/test_model_runner.py`: mocked tests. No live model is required in CI.

## Provisional model

The first provisional model is `Qwen/Qwen3-4B-Instruct-2507`.

Reasons:

- 4B size is realistic for local quantised testing.
- Apache 2.0 licence.
- It is an instruction model with non-thinking output, which avoids hidden or visible reasoning blocks.
- The official model card provides Transformers and OpenAI-compatible server examples and points to local quantisations.
- The final choice remains provisional until Task 25 factual and safety evaluation.

## Runtime design

The runner uses the OpenAI-compatible `POST /v1/chat/completions` format. This keeps the AquaBlend code independent of one model runtime. A local Ollama, vLLM, SGLang, LM Studio, or another compatible server can be used by changing `base_url` and `model_id`.

The default example is:

```json
{
  "model_id": "Qwen/Qwen3-4B-Instruct-2507",
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama",
  "temperature": 0.0,
  "top_p": 1.0,
  "max_tokens": 1200,
  "timeout_seconds": 30.0,
  "seed": 0
}
```

A runtime may use a different local model alias. Record the exact alias used in the real test configuration and test notes.

## Example usage

```python
from model_runner import load_model_config, rewrite_report

config = load_model_config("model_config.json")
result = rewrite_report(deterministic_report, config)

print(result.to_dict())
```

Important: do not display `result.report_text` as an approved LLM explanation when `report_mode` is `LLM_UNVALIDATED`. Task 25 must validate it first.

## Safe fallback behaviour

The deterministic report is returned with `report_mode="TEMPLATE_FALLBACK"` when:

- the endpoint is unavailable;
- the request times out;
- the response is malformed;
- the response is empty;
- the model returns `[REWRITE_FAILED]`;
- another runtime error occurs.

The result records:

- model ID;
- prompt version;
- runtime in milliseconds;
- whether fallback was used;
- failure type and message.

## Run tests

From the repository root:

```bash
python -m pytest ai/explanations/tests/test_model_runner.py
```

The tests use mocked model responses and do not download or start a model.

## Limitations

- This task does not prove factual faithfulness. Task 25 performs that validation.
- The official model pages do not state one universal consumer-GPU minimum. Quantised memory use and speed must be measured on the project laptop.
- `temperature=0` and a fixed seed reduce variation, but exact reproducibility can still depend on the runtime, model build, quantisation, and hardware.
