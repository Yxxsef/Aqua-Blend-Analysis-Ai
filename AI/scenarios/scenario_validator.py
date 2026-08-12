"""
AquaBlend Sprint 2 - Task 20 scenario validator.

Review update aligned with the current MILP input contract.

Key behaviours:
- validates scenario-input structure and rejects unknown/output-only fields;
- supports the current plant minimum-capacity field plus the documented legacy fallback;
- compares known arrays by stable IDs instead of list position;
- validates normal, dry-year, high-demand and plant-outage variants;
- performs conservative pre-solve capacity/connectivity screening;
- never runs the MILP or creates solver outputs/status.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence


@dataclass
class ValidationReport:
    scenario_id: str | None
    scenario_type: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changes_from_reference: list[dict[str, Any]] = field(default_factory=list)
    capacity_check: dict[str, Any] = field(default_factory=dict)
    connectivity_check: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScenarioValidator:
    SCENARIO_TYPES = ("NORMAL", "DRY_YEAR", "HIGH_DEMAND", "PLANT_OUTAGE")

    STABLE_SCENARIO_IDS = {
        "NORMAL": "toy_model_normal_year",
        "DRY_YEAR": "toy_model_dry_year",
        "HIGH_DEMAND": "scenario_2026_07_17_high_demand",
        "PLANT_OUTAGE": "scenario_2026_07_17_plant_outage",
    }

    TOP_LEVEL_REQUIRED = {
        "scenario_id", "scenario_name", "data_source",
        "sources", "network", "quality_limits",
    }
    TOP_LEVEL_ALLOWED = TOP_LEVEL_REQUIRED | {
        "status", "description", "validation", "treatment",
    }

    DATA_SOURCE_ALLOWED = {
        "type", "view", "source_rows", "rows", "allow_estimated_values",
    }
    VALIDATION_ALLOWED = {
        "fail_if_source_missing_from_database",
        "fail_if_daily_availability_missing",
        "fail_if_required_quality_value_missing",
        "fail_if_demand_missing",
    }
    SOURCE_ALLOWED = {
        "source_id", "enabled", "forced_inactive",
        "minimum_withdrawal_ml_per_day",
        "max_available_ml_per_day_override",
    }
    NETWORK_REQUIRED = {
        "plants", "demand_zones",
        "source_to_plant_links", "plant_to_zone_links",
    }
    PLANT_ALLOWED = {
        "plant_id", "name", "enabled",
        "minimum_processing_capacity_ml_per_day",
        "minimum_operating_flow_ml_per_day",  # documented legacy fallback
        "maximum_processing_capacity_ml_per_day",
        "fixed_activation_cost", "treatment_cost_per_ml",
    }
    DEMAND_ZONE_ALLOWED = {
        "zone_id", "name", "demand_ml_per_day", "demand_must_be_met",
    }
    SOURCE_TO_PLANT_LINK_ALLOWED = {
        "source_id", "plant_id", "enabled", "maximum_flow_ml_per_day",
    }
    PLANT_TO_ZONE_LINK_ALLOWED = {
        "plant_id", "zone_id", "enabled", "maximum_flow_ml_per_day",
    }
    QUALITY_LIMIT_ALLOWED = {"applies_to", "parameters"}
    QUALITY_PARAMETER_ALLOWED = {
        "unit", "min", "max", "transform",
        "source_field", "model_name", "model_unit",
        "estimated_field", "provenance_field",
    }

    OUTPUT_ONLY_FIELDS = {
        "objective", "total_cost", "volume_drawn_ml_per_day",
        "volume_supplied_ml_per_day", "percent_of_blend",
        "binding_constraints_summary", "water_quality", "diagnostics",
        "data_flags", "alternatives", "sensitivity_to_key_assumptions",
        "selected_sources", "unused_sources", "solver_status", "status_message",
    }

    METADATA_PATHS = {"scenario_id", "scenario_name", "description"}

    ALLOWED_CHANGE_PATHS = {
        "NORMAL": set(),
        "DRY_YEAR": {
            "network.source_to_plant_links[source_id=silvan_reservoir,plant_id=facility_1].maximum_flow_ml_per_day",
            "network.source_to_plant_links[source_id=yarra_kew,plant_id=facility_1].maximum_flow_ml_per_day",
            "network.source_to_plant_links[source_id=groundwater_bore_1,plant_id=facility_1].maximum_flow_ml_per_day",
        },
        "HIGH_DEMAND": {
            "network.demand_zones[zone_id=zone_1].demand_ml_per_day",
        },
        "PLANT_OUTAGE": {
            "network.plants[plant_id=facility_1].enabled",
        },
    }

    IDENTITY_FIELDS_BY_PATH = {
        "sources": ("source_id",),
        "network.plants": ("plant_id",),
        "network.demand_zones": ("zone_id",),
        "network.source_to_plant_links": ("source_id", "plant_id"),
        "network.plant_to_zone_links": ("plant_id", "zone_id"),
    }

    EXPECTED_DRY_YEAR_LINK_CAPACITIES = {
        ("silvan_reservoir", "facility_1"): 280,
        ("yarra_kew", "facility_1"): 240,
        ("groundwater_bore_1", "facility_1"): 45,
    }

    def validate(
        self,
        scenario: Mapping[str, Any],
        *,
        reference: Mapping[str, Any] | None = None,
        scenario_type: str | None = None,
    ) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(scenario, Mapping):
            return ValidationReport(
                scenario_id=None,
                scenario_type="UNKNOWN",
                valid=False,
                errors=["Scenario must be a JSON object."],
            )

        inferred_type = self._normalise_scenario_type(
            scenario_type or self.infer_scenario_type(scenario)
        )
        scenario_id = (
            scenario.get("scenario_id")
            if isinstance(scenario.get("scenario_id"), str)
            else None
        )

        self._validate_object_fields(
            scenario,
            required=self.TOP_LEVEL_REQUIRED,
            allowed=self.TOP_LEVEL_ALLOWED,
            path="root",
            errors=errors,
        )
        self._validate_top_level_types(scenario, errors)
        self._reject_output_only_fields(scenario, errors)
        self._validate_data_source(scenario.get("data_source"), errors)
        self._validate_validation_block(scenario.get("validation"), errors)
        source_ids = self._validate_sources(scenario.get("sources"), errors)
        self._validate_network(scenario.get("network"), source_ids, errors)
        self._validate_quality_limits(scenario.get("quality_limits"), errors)
        self._validate_treatment(scenario.get("treatment"), errors)

        if inferred_type == "UNKNOWN":
            errors.append(
                "Unable to assign a supported scenario type. Expected one of: "
                + ", ".join(self.SCENARIO_TYPES)
            )
        else:
            self._validate_stable_scenario_id(
                scenario.get("scenario_id"), inferred_type, errors
            )

        changes: list[dict[str, Any]] = []
        if reference is None:
            warnings.append(
                "No reference input supplied; strict scenario-difference checks "
                "were not performed."
            )
        elif isinstance(reference, Mapping):
            changes = self.diff_scenarios(reference, scenario)
            self._validate_scenario_changes(
                scenario, inferred_type, changes, errors
            )
        else:
            errors.append("Reference input must be a JSON object.")

        capacity = self.check_capacity(scenario)
        connectivity = self.check_connectivity(scenario)

        if capacity["possible_infeasible"]:
            warnings.append(capacity["message"])
        if not connectivity["all_required_zones_reachable"]:
            warnings.append(connectivity["message"])

        for plant in self._safe_list(
            scenario.get("network", {}).get("plants", [])
        ):
            if (
                isinstance(plant, Mapping)
                and "minimum_processing_capacity_ml_per_day" not in plant
                and "minimum_operating_flow_ml_per_day" in plant
            ):
                warnings.append(
                    f"Plant {plant.get('plant_id', '<unknown>')} uses the "
                    "documented legacy 'minimum_operating_flow_ml_per_day' field. "
                    "The current preferred field is "
                    "'minimum_processing_capacity_ml_per_day'."
                )

        return ValidationReport(
            scenario_id=scenario_id,
            scenario_type=inferred_type,
            valid=not errors,
            errors=errors,
            warnings=warnings,
            changes_from_reference=changes,
            capacity_check=capacity,
            connectivity_check=connectivity,
        )

    @classmethod
    def infer_scenario_type(cls, scenario: Mapping[str, Any]) -> str:
        text = " ".join(
            str(scenario.get(key, "")).lower()
            for key in ("scenario_id", "scenario_name", "description")
        )
        if "plant_outage" in text or "plant-outage" in text:
            return "PLANT_OUTAGE"
        if "high_demand" in text or "high-demand" in text:
            return "HIGH_DEMAND"
        if "dry_year" in text or "dry-year" in text:
            return "DRY_YEAR"
        if "normal_year" in text or "normal-year" in text:
            return "NORMAL"
        return "UNKNOWN"

    @classmethod
    def _normalise_scenario_type(cls, value: str) -> str:
        normalised = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "NORMAL_YEAR": "NORMAL",
            "DRY": "DRY_YEAR",
            "HIGH": "HIGH_DEMAND",
            "OUTAGE": "PLANT_OUTAGE",
        }
        normalised = aliases.get(normalised, normalised)
        return normalised if normalised in cls.SCENARIO_TYPES else "UNKNOWN"

    def _validate_top_level_types(
        self, scenario: Mapping[str, Any], errors: list[str]
    ) -> None:
        for key in ("scenario_id", "scenario_name", "status", "description"):
            if key in scenario and not isinstance(scenario[key], str):
                errors.append(f"{key} must be a string.")

        expected = {
            "data_source": Mapping,
            "validation": Mapping,
            "sources": list,
            "network": Mapping,
            "quality_limits": Mapping,
            "treatment": Mapping,
        }
        for key, expected_type in expected.items():
            if key in scenario and not isinstance(scenario[key], expected_type):
                errors.append(f"{key} has an invalid type.")

    def _validate_data_source(self, value: Any, errors: list[str]) -> None:
        if not isinstance(value, Mapping):
            return

        self._validate_object_fields(
            value,
            required={"type"},
            allowed=self.DATA_SOURCE_ALLOWED,
            path="data_source",
            errors=errors,
        )

        data_type = self._require_string(value, "type", "data_source", errors)
        if data_type is None:
            return

        normalised = data_type.lower()
        if normalised not in {"supabase", "inline"}:
            errors.append("data_source.type must be 'supabase' or 'inline'.")
            return

        if normalised == "supabase":
            self._require_string(value, "view", "data_source", errors)
        else:
            rows = value.get("source_rows", value.get("rows"))
            if not isinstance(rows, list):
                errors.append(
                    "data_source.source_rows (or rows alias) must be an array "
                    "when data_source.type is 'inline'."
                )

        if "allow_estimated_values" in value:
            self._require_bool(
                value, "allow_estimated_values", "data_source", errors
            )

    def _validate_validation_block(self, value: Any, errors: list[str]) -> None:
        if value is None:
            return
        if not isinstance(value, Mapping):
            return

        self._validate_object_fields(
            value,
            required=set(),
            allowed=self.VALIDATION_ALLOWED,
            path="validation",
            errors=errors,
        )
        for key in value:
            self._require_bool(value, key, "validation", errors)

    def _validate_sources(self, value: Any, errors: list[str]) -> set[str]:
        if not isinstance(value, list):
            return set()
        if not value:
            errors.append("sources must contain at least one source.")

        ids: list[str] = []
        for index, source in enumerate(value):
            path = f"sources[{index}]"
            if not isinstance(source, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                source,
                required={"source_id"},
                allowed=self.SOURCE_ALLOWED,
                path=path,
                errors=errors,
            )

            source_id = self._require_string(source, "source_id", path, errors)
            if source_id is not None:
                ids.append(source_id)

            if "enabled" in source:
                self._require_bool(source, "enabled", path, errors)
            if "forced_inactive" in source:
                self._require_bool(source, "forced_inactive", path, errors)
            if "minimum_withdrawal_ml_per_day" in source:
                self._require_nonnegative_number(
                    source, "minimum_withdrawal_ml_per_day", path, errors
                )

            override = source.get("max_available_ml_per_day_override")
            if override is not None and not self._is_nonnegative_number(override):
                errors.append(
                    f"{path}.max_available_ml_per_day_override must be null "
                    "or a non-negative number."
                )

        self._add_duplicate_errors(ids, "source_id", errors)
        return set(ids)

    def _validate_network(
        self,
        value: Any,
        source_ids: set[str],
        errors: list[str],
    ) -> None:
        if not isinstance(value, Mapping):
            return

        self._validate_object_fields(
            value,
            required=self.NETWORK_REQUIRED,
            allowed=self.NETWORK_REQUIRED,
            path="network",
            errors=errors,
        )

        plant_ids = self._validate_plants(value.get("plants"), errors)
        zone_ids = self._validate_demand_zones(value.get("demand_zones"), errors)
        self._validate_source_to_plant_links(
            value.get("source_to_plant_links"),
            source_ids, plant_ids, errors
        )
        self._validate_plant_to_zone_links(
            value.get("plant_to_zone_links"),
            plant_ids, zone_ids, errors
        )

    def _validate_plants(self, value: Any, errors: list[str]) -> set[str]:
        if not isinstance(value, list):
            if value is not None:
                errors.append("network.plants must be a list.")
            return set()
        if not value:
            errors.append("network.plants must contain at least one plant.")

        ids: list[str] = []
        for index, plant in enumerate(value):
            path = f"network.plants[{index}]"
            if not isinstance(plant, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                plant,
                required={"plant_id", "name"},
                allowed=self.PLANT_ALLOWED,
                path=path,
                errors=errors,
            )

            plant_id = self._require_string(plant, "plant_id", path, errors)
            if plant_id is not None:
                ids.append(plant_id)
            self._require_string(plant, "name", path, errors)

            if "enabled" in plant:
                self._require_bool(plant, "enabled", path, errors)

            minimum = self._plant_minimum_capacity(plant)
            if minimum is not None and not self._is_nonnegative_number(minimum):
                errors.append(
                    f"{path}.minimum processing capacity must be "
                    "a non-negative number."
                )

            for key in (
                "maximum_processing_capacity_ml_per_day",
                "fixed_activation_cost",
                "treatment_cost_per_ml",
            ):
                if key in plant and plant.get(key) is not None:
                    self._require_nonnegative_number(plant, key, path, errors)

            maximum = plant.get("maximum_processing_capacity_ml_per_day")
            if (
                self._is_number(minimum)
                and self._is_number(maximum)
                and minimum > maximum
            ):
                errors.append(
                    f"{path}.minimum processing capacity cannot exceed "
                    "maximum_processing_capacity_ml_per_day."
                )

        self._add_duplicate_errors(ids, "plant_id", errors)
        return set(ids)

    def _validate_demand_zones(self, value: Any, errors: list[str]) -> set[str]:
        if not isinstance(value, list):
            if value is not None:
                errors.append("network.demand_zones must be a list.")
            return set()

        ids: list[str] = []
        for index, zone in enumerate(value):
            path = f"network.demand_zones[{index}]"
            if not isinstance(zone, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                zone,
                required={"zone_id", "name"},
                allowed=self.DEMAND_ZONE_ALLOWED,
                path=path,
                errors=errors,
            )

            zone_id = self._require_string(zone, "zone_id", path, errors)
            if zone_id is not None:
                ids.append(zone_id)
            self._require_string(zone, "name", path, errors)

            if (
                "demand_ml_per_day" in zone
                and zone.get("demand_ml_per_day") is not None
            ):
                self._require_nonnegative_number(
                    zone, "demand_ml_per_day", path, errors
                )
            if "demand_must_be_met" in zone:
                self._require_bool(zone, "demand_must_be_met", path, errors)

        self._add_duplicate_errors(ids, "zone_id", errors)
        return set(ids)

    def _validate_source_to_plant_links(
        self,
        value: Any,
        source_ids: set[str],
        plant_ids: set[str],
        errors: list[str],
    ) -> None:
        if not isinstance(value, list):
            if value is not None:
                errors.append("network.source_to_plant_links must be a list.")
            return

        seen: set[tuple[str, str]] = set()
        for index, link in enumerate(value):
            path = f"network.source_to_plant_links[{index}]"
            if not isinstance(link, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                link,
                required={"source_id", "plant_id"},
                allowed=self.SOURCE_TO_PLANT_LINK_ALLOWED,
                path=path,
                errors=errors,
            )

            source_id = self._require_string(link, "source_id", path, errors)
            plant_id = self._require_string(link, "plant_id", path, errors)

            if "enabled" in link:
                self._require_bool(link, "enabled", path, errors)
            if (
                "maximum_flow_ml_per_day" in link
                and link.get("maximum_flow_ml_per_day") is not None
            ):
                self._require_nonnegative_number(
                    link, "maximum_flow_ml_per_day", path, errors
                )

            if source_id and source_id not in source_ids:
                errors.append(
                    f"{path}.source_id references an unknown source: {source_id}"
                )
            if plant_id and plant_id not in plant_ids:
                errors.append(
                    f"{path}.plant_id references an unknown plant: {plant_id}"
                )

            if source_id and plant_id:
                pair = (source_id, plant_id)
                if pair in seen:
                    errors.append(
                        f"Duplicate source-to-plant link: "
                        f"{source_id} -> {plant_id}"
                    )
                seen.add(pair)

    def _validate_plant_to_zone_links(
        self,
        value: Any,
        plant_ids: set[str],
        zone_ids: set[str],
        errors: list[str],
    ) -> None:
        if not isinstance(value, list):
            if value is not None:
                errors.append("network.plant_to_zone_links must be a list.")
            return

        seen: set[tuple[str, str]] = set()
        for index, link in enumerate(value):
            path = f"network.plant_to_zone_links[{index}]"
            if not isinstance(link, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                link,
                required={"plant_id", "zone_id"},
                allowed=self.PLANT_TO_ZONE_LINK_ALLOWED,
                path=path,
                errors=errors,
            )

            plant_id = self._require_string(link, "plant_id", path, errors)
            zone_id = self._require_string(link, "zone_id", path, errors)

            if "enabled" in link:
                self._require_bool(link, "enabled", path, errors)
            if (
                "maximum_flow_ml_per_day" in link
                and link.get("maximum_flow_ml_per_day") is not None
            ):
                self._require_nonnegative_number(
                    link, "maximum_flow_ml_per_day", path, errors
                )

            if plant_id and plant_id not in plant_ids:
                errors.append(
                    f"{path}.plant_id references an unknown plant: {plant_id}"
                )
            if zone_id and zone_id not in zone_ids:
                errors.append(
                    f"{path}.zone_id references an unknown zone: {zone_id}"
                )

            if plant_id and zone_id:
                pair = (plant_id, zone_id)
                if pair in seen:
                    errors.append(
                        f"Duplicate plant-to-zone link: {plant_id} -> {zone_id}"
                    )
                seen.add(pair)

    def _validate_quality_limits(
        self, value: Any, errors: list[str]
    ) -> None:
        if not isinstance(value, Mapping):
            return

        self._validate_object_fields(
            value,
            required={"applies_to", "parameters"},
            allowed=self.QUALITY_LIMIT_ALLOWED,
            path="quality_limits",
            errors=errors,
        )

        if value.get("applies_to") != "blend_at_plant_inflow":
            errors.append(
                "quality_limits.applies_to must be 'blend_at_plant_inflow'."
            )

        parameters = value.get("parameters")
        if not isinstance(parameters, Mapping):
            errors.append("quality_limits.parameters must be an object.")
            return

        for name, parameter in parameters.items():
            path = f"quality_limits.parameters.{name}"
            if not isinstance(parameter, Mapping):
                errors.append(f"{path} must be an object.")
                continue

            self._validate_object_fields(
                parameter,
                required={"unit", "min", "max"},
                allowed=self.QUALITY_PARAMETER_ALLOWED,
                path=path,
                errors=errors,
            )

            self._require_string(parameter, "unit", path, errors)
            self._require_number(parameter, "min", path, errors)
            self._require_number(parameter, "max", path, errors)

            if "transform" in parameter:
                self._require_string(parameter, "transform", path, errors)

            minimum = parameter.get("min")
            maximum = parameter.get("max")
            if (
                self._is_number(minimum)
                and self._is_number(maximum)
                and minimum > maximum
            ):
                errors.append(f"{path}.min cannot exceed {path}.max.")

    @staticmethod
    def _validate_treatment(value: Any, errors: list[str]) -> None:
        if value is not None and not isinstance(value, Mapping):
            errors.append("treatment must be an object.")

    def _validate_stable_scenario_id(
        self, value: Any, scenario_type: str, errors: list[str]
    ) -> None:
        expected = self.STABLE_SCENARIO_IDS.get(scenario_type)
        if not isinstance(value, str) or not value.strip():
            errors.append("scenario_id must be a non-empty string.")
        elif expected and value != expected:
            errors.append(
                f"Stable scenario_id for {scenario_type} must be "
                f"'{expected}', received '{value}'."
            )

    def _validate_scenario_changes(
        self,
        scenario: Mapping[str, Any],
        scenario_type: str,
        changes: list[dict[str, Any]],
        errors: list[str],
    ) -> None:
        if scenario_type == "UNKNOWN":
            return

        changed_paths = {change["path"] for change in changes}
        permitted = self.METADATA_PATHS | self.ALLOWED_CHANGE_PATHS[scenario_type]
        unexpected = sorted(path for path in changed_paths if path not in permitted)

        if unexpected:
            errors.append(
                f"{scenario_type} contains unapproved changes: "
                + ", ".join(unexpected)
            )

        if scenario_type == "NORMAL":
            operational = changed_paths - self.METADATA_PATHS
            if operational:
                errors.append(
                    "Normal scenario does not match the approved reference input."
                )
        elif scenario_type == "DRY_YEAR":
            self._check_source_link_values(
                scenario,
                self.EXPECTED_DRY_YEAR_LINK_CAPACITIES,
                errors,
            )
            self._require_zone_demand(scenario, "zone_1", 500, errors)
        elif scenario_type == "HIGH_DEMAND":
            self._require_zone_demand(scenario, "zone_1", 600, errors)
        elif scenario_type == "PLANT_OUTAGE":
            plant = self._find_by_id(
                scenario.get("network", {}).get("plants", []),
                "plant_id",
                "facility_1",
            )
            if plant is None or plant.get("enabled") is not False:
                errors.append(
                    "Plant-outage scenario must set "
                    "network.plants[plant_id=facility_1].enabled to false."
                )
            self._require_zone_demand(scenario, "zone_1", 500, errors)

    def _check_source_link_values(
        self,
        scenario: Mapping[str, Any],
        expected: Mapping[tuple[str, str], float],
        errors: list[str],
    ) -> None:
        links = scenario.get("network", {}).get("source_to_plant_links", [])
        actual = {
            (link.get("source_id"), link.get("plant_id")):
                link.get("maximum_flow_ml_per_day")
            for link in links
            if isinstance(link, Mapping)
        }

        for pair, expected_value in expected.items():
            if actual.get(pair) != expected_value:
                source_id, plant_id = pair
                errors.append(
                    f"Dry-year maximum flow for {source_id} -> {plant_id} "
                    f"must be {expected_value} ML/day."
                )

    def _require_zone_demand(
        self,
        scenario: Mapping[str, Any],
        zone_id: str,
        expected: float,
        errors: list[str],
    ) -> None:
        zone = self._find_by_id(
            scenario.get("network", {}).get("demand_zones", []),
            "zone_id",
            zone_id,
        )
        if zone is None or zone.get("demand_ml_per_day") != expected:
            errors.append(
                f"Scenario demand for {zone_id} must be {expected} ML/day."
            )

    def check_capacity(self, scenario: Mapping[str, Any]) -> dict[str, Any]:
        network = scenario.get("network", {})
        if not isinstance(network, Mapping):
            return self._empty_capacity_result("network is unavailable")

        sources = {
            item.get("source_id"): item
            for item in self._safe_list(scenario.get("sources", []))
            if isinstance(item, Mapping)
        }
        plants = {
            item.get("plant_id"): item
            for item in self._safe_list(network.get("plants", []))
            if isinstance(item, Mapping)
        }

        source_link_capacity = 0.0
        for link in self._safe_list(network.get("source_to_plant_links", [])):
            if not isinstance(link, Mapping) or not self._enabled(link):
                continue
            source = sources.get(link.get("source_id"))
            plant = plants.get(link.get("plant_id"))
            if not source or not plant:
                continue

            source_active = (
                self._enabled(source)
                and source.get("forced_inactive") is not True
            )
            maximum_flow = link.get("maximum_flow_ml_per_day")
            if (
                source_active
                and self._enabled(plant)
                and self._is_number(maximum_flow)
            ):
                source_link_capacity += float(maximum_flow)

        active_plant_capacity = sum(
            float(plant["maximum_processing_capacity_ml_per_day"])
            for plant in plants.values()
            if (
                self._enabled(plant)
                and self._is_number(
                    plant.get("maximum_processing_capacity_ml_per_day")
                )
            )
        )

        plant_zone_capacity = 0.0
        for link in self._safe_list(network.get("plant_to_zone_links", [])):
            if not isinstance(link, Mapping) or not self._enabled(link):
                continue
            plant = plants.get(link.get("plant_id"))
            maximum_flow = link.get("maximum_flow_ml_per_day")
            if (
                plant
                and self._enabled(plant)
                and self._is_number(maximum_flow)
            ):
                plant_zone_capacity += float(maximum_flow)

        required_demand = sum(
            float(zone["demand_ml_per_day"])
            for zone in self._safe_list(network.get("demand_zones", []))
            if (
                isinstance(zone, Mapping)
                and zone.get("demand_must_be_met", True) is True
                and self._is_number(zone.get("demand_ml_per_day"))
            )
        )

        effective_capacity = min(
            source_link_capacity,
            active_plant_capacity,
            plant_zone_capacity,
        )
        remaining = effective_capacity - required_demand
        possible_infeasible = effective_capacity < required_demand

        message = (
            "Static capacity check indicates possible infeasibility: "
            f"effective capacity {effective_capacity:g} ML/day is below "
            f"required demand {required_demand:g} ML/day."
            if possible_infeasible
            else
            "Static capacity check does not prove MILP feasibility; "
            f"remaining aggregate capacity is {remaining:g} ML/day."
        )

        return {
            "required_demand_ml_per_day": required_demand,
            "active_source_link_capacity_ml_per_day": source_link_capacity,
            "active_plant_capacity_ml_per_day": active_plant_capacity,
            "active_plant_to_zone_capacity_ml_per_day": plant_zone_capacity,
            "effective_capacity_ml_per_day": effective_capacity,
            "remaining_capacity_ml_per_day": remaining,
            "possible_infeasible": possible_infeasible,
            "message": message,
        }

    def check_connectivity(self, scenario: Mapping[str, Any]) -> dict[str, Any]:
        network = scenario.get("network", {})
        if not isinstance(network, Mapping):
            return {
                "all_required_zones_reachable": False,
                "unreachable_zone_ids": [],
                "message": (
                    "Connectivity could not be checked because network is unavailable."
                ),
            }

        active_sources = {
            source.get("source_id")
            for source in self._safe_list(scenario.get("sources", []))
            if (
                isinstance(source, Mapping)
                and self._enabled(source)
                and source.get("forced_inactive") is not True
            )
        }
        active_plants = {
            plant.get("plant_id")
            for plant in self._safe_list(network.get("plants", []))
            if isinstance(plant, Mapping) and self._enabled(plant)
        }

        reachable_plants = {
            link.get("plant_id")
            for link in self._safe_list(network.get("source_to_plant_links", []))
            if (
                isinstance(link, Mapping)
                and self._enabled(link)
                and link.get("source_id") in active_sources
                and link.get("plant_id") in active_plants
                and self._positive(link.get("maximum_flow_ml_per_day"))
            )
        }

        reachable_zones = {
            link.get("zone_id")
            for link in self._safe_list(network.get("plant_to_zone_links", []))
            if (
                isinstance(link, Mapping)
                and self._enabled(link)
                and link.get("plant_id") in reachable_plants
                and self._positive(link.get("maximum_flow_ml_per_day"))
            )
        }

        required_zones = {
            zone.get("zone_id")
            for zone in self._safe_list(network.get("demand_zones", []))
            if (
                isinstance(zone, Mapping)
                and zone.get("demand_must_be_met", True) is True
                and self._positive(zone.get("demand_ml_per_day"))
            )
        }

        unreachable = sorted(
            zone for zone in required_zones if zone not in reachable_zones
        )
        reachable = not unreachable

        return {
            "all_required_zones_reachable": reachable,
            "unreachable_zone_ids": unreachable,
            "message": (
                "All mandatory-demand zones have an active "
                "source-to-plant-to-zone path."
                if reachable
                else
                "No active treatment path exists for required zone(s): "
                + ", ".join(unreachable)
                + ". This indicates possible infeasibility before solving."
            ),
        }

    @classmethod
    def diff_scenarios(
        cls,
        reference: Mapping[str, Any],
        scenario: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        differences: list[dict[str, Any]] = []
        cls._diff_values(reference, scenario, "", differences)
        return differences

    @classmethod
    def _diff_values(
        cls,
        before: Any,
        after: Any,
        path: str,
        differences: list[dict[str, Any]],
    ) -> None:
        if isinstance(before, Mapping) and isinstance(after, Mapping):
            for key in sorted(set(before) | set(after)):
                child_path = f"{path}.{key}" if path else key
                if key not in before:
                    differences.append(
                        {"path": child_path, "before": "<missing>", "after": after[key]}
                    )
                elif key not in after:
                    differences.append(
                        {"path": child_path, "before": before[key], "after": "<missing>"}
                    )
                else:
                    cls._diff_values(
                        before[key], after[key], child_path, differences
                    )
            return

        if isinstance(before, list) and isinstance(after, list):
            identity_fields = cls.IDENTITY_FIELDS_BY_PATH.get(path)
            if identity_fields:
                before_map = cls._index_list(before, identity_fields)
                after_map = cls._index_list(after, identity_fields)

                if before_map is not None and after_map is not None:
                    keys = sorted(
                        set(before_map) | set(after_map),
                        key=lambda item: tuple(str(part) for part in item),
                    )
                    for identity in keys:
                        selector = ",".join(
                            f"{field}={value}"
                            for field, value in zip(identity_fields, identity)
                        )
                        child_path = f"{path}[{selector}]"

                        if identity not in before_map:
                            differences.append(
                                {
                                    "path": child_path,
                                    "before": "<missing>",
                                    "after": after_map[identity],
                                }
                            )
                        elif identity not in after_map:
                            differences.append(
                                {
                                    "path": child_path,
                                    "before": before_map[identity],
                                    "after": "<missing>",
                                }
                            )
                        else:
                            cls._diff_values(
                                before_map[identity],
                                after_map[identity],
                                child_path,
                                differences,
                            )
                    return

            maximum = max(len(before), len(after))
            for index in range(maximum):
                child_path = f"{path}[{index}]"
                if index >= len(before):
                    differences.append(
                        {"path": child_path, "before": "<missing>", "after": after[index]}
                    )
                elif index >= len(after):
                    differences.append(
                        {"path": child_path, "before": before[index], "after": "<missing>"}
                    )
                else:
                    cls._diff_values(
                        before[index], after[index], child_path, differences
                    )
            return

        if before != after:
            differences.append(
                {"path": path, "before": before, "after": after}
            )

    @staticmethod
    def _index_list(
        items: list[Any],
        identity_fields: tuple[str, ...],
    ) -> dict[tuple[Any, ...], Mapping[str, Any]] | None:
        result: dict[tuple[Any, ...], Mapping[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                return None
            identity = tuple(item.get(field) for field in identity_fields)
            if any(value is None for value in identity) or identity in result:
                return None
            result[identity] = item
        return result

    def _reject_output_only_fields(
        self, scenario: Mapping[str, Any], errors: list[str]
    ) -> None:
        found: list[str] = []

        def walk(value: Any, path: str) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    child_path = f"{path}.{key}" if path else key
                    if key in self.OUTPUT_ONLY_FIELDS:
                        found.append(child_path)
                    walk(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")

        walk(scenario, "")
        if found:
            errors.append(
                "Output-only fields are not permitted in scenario inputs: "
                + ", ".join(sorted(found))
            )

    @staticmethod
    def _validate_object_fields(
        value: Mapping[str, Any],
        *,
        required: set[str],
        allowed: set[str],
        path: str,
        errors: list[str],
    ) -> None:
        actual = set(value)
        missing = sorted(required - actual)
        unknown = sorted(actual - allowed)

        if missing:
            errors.append(
                f"{path} is missing required field(s): {', '.join(missing)}"
            )
        if unknown:
            errors.append(
                f"{path} contains unknown field(s): {', '.join(unknown)}"
            )

    @staticmethod
    def _require_string(
        value: Mapping[str, Any],
        key: str,
        path: str,
        errors: list[str],
    ) -> str | None:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}.{key} must be a non-empty string.")
            return None
        return item

    @staticmethod
    def _require_bool(
        value: Mapping[str, Any],
        key: str,
        path: str,
        errors: list[str],
    ) -> None:
        if not isinstance(value.get(key), bool):
            errors.append(f"{path}.{key} must be true or false.")

    @classmethod
    def _require_number(
        cls,
        value: Mapping[str, Any],
        key: str,
        path: str,
        errors: list[str],
    ) -> None:
        if not cls._is_number(value.get(key)):
            errors.append(f"{path}.{key} must be a number.")

    @classmethod
    def _require_nonnegative_number(
        cls,
        value: Mapping[str, Any],
        key: str,
        path: str,
        errors: list[str],
    ) -> None:
        if not cls._is_nonnegative_number(value.get(key)):
            errors.append(f"{path}.{key} must be a non-negative number.")

    @staticmethod
    def _add_duplicate_errors(
        values: Sequence[str],
        label: str,
        errors: list[str],
    ) -> None:
        duplicates = sorted({item for item in values if values.count(item) > 1})
        if duplicates:
            errors.append(
                f"Duplicate {label} value(s): {', '.join(duplicates)}"
            )

    @staticmethod
    def _find_by_id(
        items: Iterable[Any], key: str, expected: str
    ) -> Mapping[str, Any] | None:
        for item in items:
            if isinstance(item, Mapping) and item.get(key) == expected:
                return item
        return None

    @staticmethod
    def _enabled(value: Mapping[str, Any]) -> bool:
        return value.get("enabled", True) is not False

    @staticmethod
    def _plant_minimum_capacity(plant: Mapping[str, Any]) -> Any:
        if "minimum_processing_capacity_ml_per_day" in plant:
            return plant.get("minimum_processing_capacity_ml_per_day")
        return plant.get("minimum_operating_flow_ml_per_day", 0)

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @classmethod
    def _is_nonnegative_number(cls, value: Any) -> bool:
        return cls._is_number(value) and value >= 0

    @classmethod
    def _positive(cls, value: Any) -> bool:
        return cls._is_number(value) and value > 0

    @staticmethod
    def _empty_capacity_result(reason: str) -> dict[str, Any]:
        return {
            "required_demand_ml_per_day": 0,
            "active_source_link_capacity_ml_per_day": 0,
            "active_plant_capacity_ml_per_day": 0,
            "active_plant_to_zone_capacity_ml_per_day": 0,
            "effective_capacity_ml_per_day": 0,
            "remaining_capacity_ml_per_day": 0,
            "possible_infeasible": True,
            "message": f"Capacity could not be checked because {reason}.",
        }


def validate_scenario(
    scenario: Mapping[str, Any],
    *,
    reference: Mapping[str, Any] | None = None,
    scenario_type: str | None = None,
) -> dict[str, Any]:
    return ScenarioValidator().validate(
        scenario,
        reference=reference,
        scenario_type=scenario_type,
    ).to_dict()


if __name__ == "__main__":
    import argparse
    import json

    try:
        from scenario_loader import load_scenario
    except ImportError:  # pragma: no cover
        from .scenario_loader import load_scenario

    parser = argparse.ArgumentParser(
        description="Validate an AquaBlend scenario."
    )
    parser.add_argument("scenario", help="Scenario JSON path")
    parser.add_argument(
        "--reference",
        help="Approved normal/reference JSON path for strict change checks",
    )
    parser.add_argument(
        "--type",
        choices=ScenarioValidator.SCENARIO_TYPES,
        help="Explicit scenario type; otherwise inferred from metadata",
    )
    args = parser.parse_args()

    parsed_scenario = load_scenario(args.scenario)
    parsed_reference = (
        load_scenario(args.reference) if args.reference else None
    )

    report = validate_scenario(
        parsed_scenario,
        reference=parsed_reference,
        scenario_type=args.type,
    )
    print(json.dumps(report, indent=2))