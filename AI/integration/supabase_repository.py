"""Supabase read/write logic for the AquaBlend Analysis & AI pipeline.

``AI/main.py`` coordinates the pipeline; every detailed Supabase query,
insert mapping, and credential check lives here instead. Local JSON mode
never imports Supabase credentials: ``_client()`` (and therefore every
public function below) only touches ``env.require_db_credentials()`` when
it is actually called, so running the pipeline against a file never
requires ``DB_URL``/``DB_KEY`` to be set.

Column names throughout this module are taken from the reference schema in
``AI/integration/supabase_schema/`` and must stay in sync with it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

import httpx
from postgrest.exceptions import APIError
from supabase import create_client

_AI_DIR = Path(__file__).resolve().parents[1]
for _module_dir in (_AI_DIR, _AI_DIR / "results" / "app_response"):
    module_dir_text = str(_module_dir)
    if module_dir_text not in sys.path:
        sys.path.insert(0, module_dir_text)

from env import require_db_credentials  # noqa: E402


class SupabaseError(RuntimeError):
    """A Supabase read or write could not be completed."""


def _client():
    """Create a Supabase client, validating credentials right before use.

    Raises:
        SupabaseError: DB_URL/DB_KEY are not set (see AI/.env.example).
    """
    try:
        db_url, db_key = require_db_credentials()
    except RuntimeError as exc:
        raise SupabaseError(str(exc)) from exc
    return create_client(supabase_url=db_url, supabase_key=db_key)


def _sha256_json(payload: Any) -> str:
    """Stable SHA-256 digest of a JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def load_milp_output(
    run_id: int | None = None,
    scenario_db_id: int | None = None,
    scenario: str | None = None,
) -> Dict[str, Any]:
    """Load one row from ``public.milp_model_output``.

    With no selector the newest row by ``created_at`` is returned. Each
    selector names the real column it filters: ``origin_run_id``,
    ``scenario_db_id`` (both nullable integers) and ``scenario_id`` (the
    varchar display string, for example "SCN-008").

    Raises:
        SupabaseError: the table could not be reached, credentials are
            missing, or no row matched.
    """
    # limit(1) rather than single(): single() raises on an empty result, which
    # is a normal state to report rather than a transport failure.
    try:
        query = _client().table("milp_model_output").select("*")

        if run_id is not None:
            query = query.eq("origin_run_id", run_id)
        if scenario_db_id is not None:
            query = query.eq("scenario_db_id", scenario_db_id)
        if scenario is not None:
            query = query.eq("scenario_id", scenario)

        rows = (
            query
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
    except SupabaseError:
        raise
    except APIError as exc:
        raise SupabaseError(f"milp_model_output query rejected: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Could not reach Supabase: {exc}") from exc
    except Exception as exc:  # Safe boundary around the client runtime.
        raise SupabaseError(f"Unexpected Supabase failure: {exc}") from exc

    if not rows:
        selectors = {
            "origin_run_id": run_id,
            "scenario_db_id": scenario_db_id,
            "scenario_id": scenario,
        }
        asked = ", ".join(
            f"{name}={value!r}"
            for name, value in selectors.items()
            if value is not None
        )
        raise SupabaseError(
            f"No milp_model_output row matched {asked}."
            if asked
            else "milp_model_output contains no rows to analyse."
        )

    return rows[0]


def load_milp_input(input_id: str) -> Dict[str, Any]:
    """Load one row from ``public.milp_model_input`` by primary key ``id``.

    Raises:
        SupabaseError: the table could not be reached, credentials are
            missing, or no row matched.
    """
    try:
        rows = (
            _client()
            .table("milp_model_input")
            .select("*")
            .eq("id", input_id)
            .limit(1)
            .execute()
            .data
        )
    except SupabaseError:
        raise
    except APIError as exc:
        raise SupabaseError(f"milp_model_input query rejected: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Could not reach Supabase: {exc}") from exc
    except Exception as exc:  # Safe boundary around the client runtime.
        raise SupabaseError(f"Unexpected Supabase failure: {exc}") from exc

    if not rows:
        raise SupabaseError(f"No milp_model_input row matched id={input_id!r}.")
    return rows[0]


# ---------------------------------------------------------------------------
# milp_model_output -> canonical Results JSON
# ---------------------------------------------------------------------------

# results_validator.REQUIRED_FIELDS, duplicated as a lightweight presence
# check here: "does raw_output_json already carry the complete canonical
# output contract" should not require importing the validator (which
# enforces far more than presence, and would turn an incomplete-but-usable
# raw_output_json into a hard failure instead of a documented fallback).
_CANONICAL_REQUIRED_FIELDS = (
    "scenario_id", "status", "objective", "demand_zones", "sources",
    "transfer_paths", "plants", "water_quality", "constraints",
    "diagnostics", "data_flags",
)


def extract_canonical_output(output_row: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """Return ``(canonical_results, warnings)`` for one ``milp_model_output`` row.

    ``raw_output_json`` is used as-is when it already contains every field
    the canonical Results JSON contract requires. Otherwise the flat,
    schema-defined columns are normalised into that shape on a best-effort
    basis (see ``normalize_output_columns``), and a warning explains the
    fallback. The database row's own metadata (``id``, ``output_hash``,
    ``origin_run_id``, ...) is never merged into the canonical payload -
    callers that need it read it from ``output_row`` directly.
    """
    raw = output_row.get("raw_output_json")
    if isinstance(raw, Mapping) and all(field in raw for field in _CANONICAL_REQUIRED_FIELDS):
        return dict(raw), []

    warning = (
        "raw_output_json did not contain the complete canonical output "
        "contract; the analysis payload was built from milp_model_output's "
        "flat columns instead. Fields with no flat-column equivalent "
        "(constraints, diagnostics, per-source provenance) are unavailable."
    )
    return normalize_output_columns(output_row), [warning]


def _split_flat_sources(sources: Any) -> tuple[list, list]:
    """Split a flat ``sources`` column into selected/unused, per the
    normalisation rules documented on ``normalize_output_columns``."""
    selected: list[Any] = []
    unused: list[Any] = []
    if not isinstance(sources, list):
        return selected, unused

    for entry in sources:
        if not isinstance(entry, Mapping):
            continue
        entry = dict(entry)
        is_selected = entry.get("selected")
        if is_selected is None:
            is_selected = entry.get("is_selected")
        if is_selected is None:
            volume = entry.get("volume_drawn_ml_per_day")
            is_selected = isinstance(volume, (int, float)) and volume > 0
        (selected if is_selected else unused).append(entry)
    return selected, unused


def normalize_output_columns(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Best-effort canonical Results JSON built from ``milp_model_output``'s
    flat columns, documented here since the flat schema does not define a
    1:1 mapping to the canonical contract:

    - ``sources`` is assumed to already use the source objects' canonical
      shape, just not yet split into ``selected``/``unused``. A source
      counts as selected when it has an explicit ``selected``/``is_selected``
      boolean, or otherwise when it reports a positive drawn volume.
    - ``plants`` is used as-is when it already has ``active``/``inactive``
      keys; otherwise every entry is treated as active (the flat column
      does not distinguish, and assuming "active" is safer than silently
      dropping a plant that was actually processing water).
    - ``flows_source_to_plant`` / ``flows_plant_to_zone`` map directly to
      ``transfer_paths.source_to_plant`` / ``transfer_paths.plant_to_zone``.
    - ``quality`` maps to ``water_quality`` as-is when it already has a
      ``by_plant`` key; otherwise it is assumed to already be a per-plant
      mapping and is nested under ``by_plant`` with ``applies_to`` left
      unset (unknown, rather than guessed).
    - ``solver_status`` maps to ``status``; ``total_cost`` (falling back to
      ``solver_objective_value``) maps to ``objective.total_cost``.
    - There is no flat-column equivalent of ``constraints`` or
      ``diagnostics``, so both are empty - the canonical contract only
      requires them to be a list/object, and downstream binding-constraint
      explanations already degrade gracefully to "no plain-language mapping
      available" for a name with no matching detail.
    - ``data_flags.sources`` cannot be reconstructed from these columns (no
      per-source provenance column exists at the flat level), so it is left
      empty. This is deliberate, not an oversight: confidence_flagger.py
      already treats an empty provenance list as UNKNOWN rather than
      failing, which is exactly the "lower confidence, don't fail the
      analysis" behaviour optional provenance data is supposed to get.
    """
    selected, unused = _split_flat_sources(row.get("sources"))

    plants_raw = row.get("plants")
    if isinstance(plants_raw, Mapping):
        active = plants_raw.get("active") or []
        inactive = plants_raw.get("inactive") or []
    elif isinstance(plants_raw, list):
        active, inactive = plants_raw, []
    else:
        active, inactive = [], []

    quality_raw = row.get("quality")
    if isinstance(quality_raw, Mapping) and "by_plant" in quality_raw:
        water_quality = dict(quality_raw)
    else:
        water_quality = {
            "applies_to": None,
            "by_plant": quality_raw if isinstance(quality_raw, Mapping) else {},
        }

    total_cost = row.get("total_cost")
    if total_cost is None:
        total_cost = row.get("solver_objective_value")

    return {
        "scenario_id": row.get("scenario_id"),
        "status": row.get("solver_status"),
        "objective": {"total_cost": total_cost},
        "demand_zones": row.get("demand_zones") or [],
        "sources": {"selected": selected, "unused": unused},
        "transfer_paths": {
            "source_to_plant": row.get("flows_source_to_plant") or [],
            "plant_to_zone": row.get("flows_plant_to_zone") or [],
        },
        "plants": {"active": active, "inactive": inactive},
        "water_quality": water_quality,
        "constraints": [],
        "diagnostics": {},
        "data_flags": {"sources": [], "notes": list(row.get("warnings") or [])},
        "binding_constraints_summary": row.get("binding_constraints_summary") or [],
    }


def load_input_provenance(output_row: Mapping[str, Any]) -> tuple[Dict[str, Any] | None, list[str]]:
    """Best-effort retrieval of the ``milp_model_input`` row linked through
    ``output_row["input_id"]``.

    KNOWN INTEGRATION BLOCKER: this only fetches the row. It does NOT map
    its fields into ``data_flags`` or otherwise feed the confidence
    calculation - no real ``milp_model_input`` row has been seen yet, so the
    JSON shape of ``scenario_data_json``/``source_data_snapshot_json`` is
    unconfirmed, and inventing a mapping now would risk fabricating a
    confidence signal from a guess. The caller (``main.run_from_source``)
    currently discards the returned dict and keeps only the warnings.

    Never raises: a missing link or an unreadable row produces a warning,
    per the pipeline rule that missing optional data must not fail the
    analysis. Returns ``(None, warnings)`` in that case.
    """
    input_id = output_row.get("input_id")
    if not input_id:
        return None, [
            "milp_model_output row has no input_id; scenario provenance "
            "from milp_model_input is unavailable."
        ]

    try:
        input_row = load_milp_input(input_id)
    except SupabaseError as exc:
        return None, [f"Linked milp_model_input row could not be read: {exc}"]

    provenance = {
        key: input_row.get(key)
        for key in (
            "scenario_data_json",
            "source_data_snapshot_json",
            "model_parameters_json",
            "validation_policy",
            "allow_estimated_values",
        )
    }
    return provenance, []


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def save_ai_output(
    response: Mapping[str, Any],
    milp_row: Mapping[str, Any],
    model_config: "ModelConfig | None" = None,
    prompt_version: str | None = None,
    latency_ms: float | None = None,
    started_at: Any = None,
) -> Dict[str, Any]:
    """Insert one App response into ``milp_ai_output`` and return the inserted row.

    Foreign keys are read from ``milp_row`` (the ``milp_model_output`` row
    the response was computed from), mapped exactly as the schema defines:
    ``id`` -> ``milp_output_id``, ``origin_run_id`` -> ``origin_run_id``,
    ``scenario_db_id`` -> ``scenario_id`` (the integer FK into Scenarios;
    ``scenario_id`` on the MILP row is the display string and must never be
    used here), ``output_hash`` -> ``milp_output_hash``.

    Sprint 4 Task 86 - column coverage (every ``milp_ai_output`` column not
    obviously populated above, classified so a later task knows exactly
    what still needs wiring up, and never mistakes "not yet available" for
    "forgotten"):

    Populated now (see the ``row`` dict below): ``milp_output_id``,
    ``scenario_id``, ``origin_run_id``, ``status``, ``ai_contract_version``,
    ``milp_output_hash``, ``ai_output_hash``, ``ai_input_json``,
    ``executive_summary``, ``decision_explanation``, ``raw_ai_json``,
    ``warnings``, ``completed_at``, ``started_at`` (when given),
    ``error_code``/``error_message`` (only on a failed analysis), ``ai_model``
    /``prompt_version`` (only when a model actually ran).

    Intentionally stored as the schema's own empty default - the pipeline
    has no analysis to put here yet, and an empty list/object is what the
    column already defaults to, so omitting the key vs. setting it
    explicitly has the same effect. Listed explicitly anyway so it is clear
    these are a deliberate "nothing to report" rather than an oversight:
    ``key_findings`` ([]), ``anomalies`` ([]), ``recommendations`` ([]),
    ``risk_assessment`` ({}), ``source_analysis`` ({}), ``plant_analysis``
    ({}), ``quality_analysis`` ({}), ``limitations`` ([]).

    Deferred - genuinely unavailable, left as SQL NULL (never set in
    ``row``, never guessed):
    - ``ai_provider``: no field anywhere carries "which vendor/host served
      this" (``ModelConfig`` only has ``base_url``, which is a detail, not
      a normalised provider name).
    - ``ai_model_version``: ``ModelConfig.model_id`` is the only model
      identifier available; there is no separate version string to read.
    - ``analysis_version``: no concept of an analysis-logic version distinct
      from ``ai_contract_version`` exists yet in this pipeline.
    - ``ai_cache_key``: no cache-key derivation has been implemented.
    - ``prompt_tokens``, ``completion_tokens``, ``total_tokens``:
      ``model_runner.rewrite_report``/``RewriteResult`` do not parse the
      OpenAI-compatible response's ``usage`` object, so no token counts are
      available to record - inventing a number here would misreport real
      model cost/usage.

    Not part of this task's required list, but also left to the DB's own
    default rather than being set here: ``cache_reusable`` (defaults
    ``true``), ``forced_recompute`` (defaults ``false``).

    Raises:
        SupabaseError: the MILP row cannot key a milp_ai_output row, the
            scenario identifier is not an integer, or the insert failed.
    """
    from app_response_adapter import validate_app_response

    validate_app_response(response)

    if not isinstance(milp_row, Mapping):
        raise SupabaseError(
            "An App response can only be saved against a MILP output row."
        )

    missing = [key for key in ("id", "scenario_db_id") if milp_row.get(key) is None]
    if missing:
        raise SupabaseError(
            "MILP output row is missing key(s) required by milp_ai_output: "
            + ", ".join(missing)
        )

    scenario_db_id = milp_row["scenario_db_id"]
    if not isinstance(scenario_db_id, int) or isinstance(scenario_db_id, bool):
        raise SupabaseError(
            "milp_model_output.scenario_db_id must be an integer to satisfy "
            "milp_ai_output.scenario_id's foreign key; got "
            f"{scenario_db_id!r}."
        )

    failed = response["report_mode"] == "INVALID_INPUT"

    row: dict[str, Any] = {
        "milp_output_id": milp_row["id"],
        "scenario_id": scenario_db_id,
        "origin_run_id": milp_row.get("origin_run_id"),
        "status": "failed" if failed else "completed",
        "ai_contract_version": response["contract_version"],
        # MILP publishes its own digest; both tables are indexed on their
        # hashes so an AI row can be matched back to the output it analysed.
        # Fall back to our own only when the column is null.
        "milp_output_hash": milp_row.get("output_hash") or _sha256_json(milp_row),
        "ai_output_hash": _sha256_json(response),
        "ai_input_json": dict(milp_row),
        "executive_summary": response["executive_summary"],
        "decision_explanation": response["detailed_explanation"],
        "raw_ai_json": dict(response),
        "key_findings": [],
        "anomalies": [],
        "recommendations": [],
        "warnings": list(response["warnings"]),
        "risk_assessment": {},
        "source_analysis": {},
        "plant_analysis": {},
        "quality_analysis": {},
        "limitations": [],
        "completed_at": _isoformat(_now_utc()),
    }

    if started_at is not None:
        row["started_at"] = _isoformat(started_at)

    # A failure belongs in the dedicated columns, not only in the warnings
    # payload, so it can be queried without unpacking jsonb.
    if failed:
        row["error_code"] = response["report_mode"]
        row["error_message"] = next(iter(response["warnings"]), None)

    # Only a model-backed run can describe which model produced the report;
    # never invent a model id, version, or prompt version that wasn't used.
    if model_config is not None:
        row["ai_model"] = model_config.model_id
    if prompt_version is not None:
        row["prompt_version"] = prompt_version
    if latency_ms is not None:
        row["latency_ms"] = latency_ms

    try:
        return _client().table("milp_ai_output").insert(row).execute().data
    except SupabaseError:
        raise
    except APIError as exc:
        raise SupabaseError(f"milp_ai_output insert rejected: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Could not reach Supabase: {exc}") from exc
    except Exception as exc:  # Safe boundary around the client runtime.
        raise SupabaseError(f"Unexpected Supabase failure: {exc}") from exc


def _now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _isoformat(value: Any) -> str:
    if isinstance(value, str):
        return value
    return value.isoformat()
