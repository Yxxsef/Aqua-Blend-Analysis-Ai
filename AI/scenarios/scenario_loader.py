"""
AquaBlend Sprint 2 - Task 20 scenario loader.

This module reads AquaBlend input-scenario JSON files using UTF-8 and returns
ordinary Python dictionaries. Contract validation is intentionally delegated to
``scenario_validator.py`` so loading and validation remain separate concerns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


class ScenarioLoadError(ValueError):
    """Raised when a scenario file exists but cannot be decoded or parsed."""


def load_scenario(file_path: str | Path) -> dict[str, Any]:
    """Load one AquaBlend scenario JSON file.

    Args:
        file_path: Path to a UTF-8 JSON file.

    Returns:
        The parsed top-level JSON object.

    Raises:
        FileNotFoundError: If ``file_path`` does not exist.
        IsADirectoryError: If ``file_path`` is a directory.
        ScenarioLoadError: If the file is not UTF-8, is malformed JSON, or its
            top-level JSON value is not an object.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"Expected a JSON file, received a directory: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ScenarioLoadError(
            f"Scenario file is not valid UTF-8: {path}"
        ) from exc
    except OSError as exc:
        raise ScenarioLoadError(f"Unable to read scenario file: {path}") from exc

    try:
        scenario = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ScenarioLoadError(
            f"Invalid JSON in {path} at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(scenario, dict):
        raise ScenarioLoadError(
            f"Scenario JSON must contain an object at the top level: {path}"
        )

    return scenario


def discover_scenario_files(
    folder_path: str | Path,
    *,
    recursive: bool = True,
) -> list[Path]:
    """Return scenario JSON paths in deterministic filename order.

    Files are selected when their filename begins with ``scenario_`` and ends
    with ``.json``. This avoids accidentally loading unrelated JSON outputs.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Scenario folder not found: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Expected a scenario folder: {folder}")

    iterator: Iterable[Path]
    iterator = (
        folder.rglob("scenario_*.json")
        if recursive
        else folder.glob("scenario_*.json")
    )
    return sorted(
        (path for path in iterator if path.is_file()),
        key=lambda path: str(path),
    )


def load_scenarios(
    folder_path: str | Path,
    *,
    recursive: bool = True,
) -> list[tuple[Path, dict[str, Any]]]:
    """Load all discovered scenario files from a folder.

    Returns:
        A list of ``(path, scenario_dict)`` tuples in deterministic order.
    """
    return [
        (path, load_scenario(path))
        for path in discover_scenario_files(folder_path, recursive=recursive)
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Load AquaBlend scenario JSON files."
    )
    parser.add_argument("path", help="Scenario JSON file or scenario folder")
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Do not search child folders when a folder is supplied",
    )
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_dir():
        loaded = load_scenarios(target, recursive=not args.non_recursive)
        for scenario_path, scenario in loaded:
            print(f"{scenario_path}: {scenario.get('scenario_id', '<missing id>')}")
        print(f"Loaded {len(loaded)} scenario file(s).")
    else:
        loaded_scenario = load_scenario(target)
        print(
            "Loaded scenario: "
            f"{loaded_scenario.get('scenario_id', '<missing id>')}"
        )
