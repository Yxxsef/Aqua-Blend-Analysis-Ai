# Task 27 Draft Package

This folder contains a first-draft implementation of **Task 27: Build the App & Delivery response adapter and mock package**.

## Included deliverables

- `app_response_adapter.py` — response adapter + structural validation + UTF-8 JSON writer.
- `test_app_response_adapter.py` — tests for success, fallback, non-optimal, invalid input, structure, and non-mutation.
- `examples/success_response.json` — validated-LLM success mock.
- `examples/fallback_response.json` — LLM-failure/template-fallback mock.
- `examples/error_response.json` — non-optimal/status-only mock.
- `examples/invalid_input_response.json` — extra invalid-input mock.
- `App_Integration_Contract.md` — documented response contract, enums, warnings, stable/draft fields, and integration notes.

## Important draft boundary

Tasks 19, 21, 23, 25 and 26 are not final yet. Their values are therefore inputs to the adapter rather than being reimplemented here. This lets App & Delivery build against one outer response shape now and lets the internal upstream payloads be tightened later.

## Run tests

```bash
python -m unittest -v test_app_response_adapter.py
```
