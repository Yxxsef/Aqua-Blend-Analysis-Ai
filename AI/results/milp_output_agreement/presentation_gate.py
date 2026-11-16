"""
Reference implementation of the Task 45 MILP output agreement.

Reads presentation_rules.json and answers two questions for one MILP output
(the parsed raw_output_json of a milp_model_output row):

- gate_mode(output): NO_SOLUTION, INVALID_OUTPUT or VALID
- presentable_values(output): every (path, value) the explanation layer may
  show to users and quote as a figure in that mode

Tasks 38 (template fallback) and 48 (LLM number verification) can use
presentable_values() as their list of allowed figures instead of each
re-deciding which fields are safe.

Standard library only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

RULES_PATH = Path(__file__).with_name("presentation_rules.json")

NO_SOLUTION = "NO_SOLUTION"
INVALID_OUTPUT = "INVALID_OUTPUT"
VALID = "VALID"


def load_rules(path: str | Path = RULES_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def leaf_paths(value: Any, prefix: str = "") -> Iterator[tuple[str, Any, dict[str, Any] | None]]:
    """Yield (path, value, parent_record) for every leaf, using [] for list items.

    parent_record is the nearest enclosing dict, so per-record conditions such
    as "transform == 'identity'" can be checked.
    """
    yield from _walk(value, prefix, None)


def _walk(value: Any, prefix: str, parent: dict[str, Any] | None):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{prefix}.{key}" if prefix else key, value)
    elif isinstance(value, list):
        if value and isinstance(value[0], (dict, list)):
            for item in value:
                yield from _walk(item, prefix + "[]", parent)
        else:
            yield prefix + "[]", value, parent
    else:
        yield prefix, value, parent


def gate_mode(output: dict[str, Any]) -> str:
    solver = output.get("solver") or {}
    if solver.get("is_feasible") is not True:
        return NO_SOLUTION
    consistency = (output.get("validation") or {}).get("output_consistency") or {}
    if str(consistency.get("status", "")).upper() != "PASSED":
        return INVALID_OUTPUT
    return VALID


def _condition_holds(condition: str | None, record: dict[str, Any] | None) -> bool:
    if not condition:
        return True
    # Only one condition form is used in the rules: "<field> == '<value>'".
    field, _, expected = condition.partition("==")
    field = field.strip()
    expected = expected.strip().strip("'\"")
    return record is not None and str(record.get(field)) == expected


def presentable_values(
    output: dict[str, Any], rules: dict[str, Any] | None = None
) -> list[tuple[str, Any]]:
    rules = rules or load_rules()
    fields = rules["fields"]
    mode = gate_mode(output)
    allowed: list[tuple[str, Any]] = []

    for path, value, record in leaf_paths(output):
        rule = fields.get(path)
        if rule is None or rule["use"] != "present":
            continue
        if not _condition_holds(rule.get("condition"), record):
            continue
        if rule["when"] == "valid" and mode != VALID:
            # Exclusion is decided before solving, so it is a fact in every mode.
            if not (path == "sources[].selection_status" and value == "EXCLUDED"):
                continue
        allowed.append((path, value))

    return allowed


if __name__ == "__main__":
    import sys

    for file_name in sys.argv[1:]:
        with open(file_name, encoding="utf-8") as handle:
            data = json.load(handle)
        print(f"{file_name}: {gate_mode(data)}")
        for path, value in presentable_values(data):
            print(f"  {path} = {value!r}")
