"""Tests for AquaBlend Sprint 2 Task 20 scenario loading and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scenario_loader import ScenarioLoadError, load_scenario
from scenario_validator import ScenarioValidator


SCENARIO_DIR = Path(__file__).resolve().parent
NORMAL_PATH = SCENARIO_DIR / "normal-year-dry-year" / "scenario_normal.json"
DRY_PATH = SCENARIO_DIR / "normal-year-dry-year" / "scenario_dry_year.json"
HIGH_PATH = SCENARIO_DIR / "high-demand-outage" / "scenario_high_demand.json"
OUTAGE_PATH = SCENARIO_DIR / "high-demand-outage" / "scenario_plant_outage.json"


class ScenarioLoaderTests(unittest.TestCase):
    """Tests for strict UTF-8 and JSON loading."""

    def test_load_valid_utf8_json(self) -> None:
        scenario = load_scenario(NORMAL_PATH)
        self.assertEqual(scenario["scenario_id"], "toy_model_normal_year")

    def test_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_scenario(SCENARIO_DIR / "does_not_exist.json")

    def test_malformed_json_raises_scenario_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "scenario_bad.json"
            path.write_text('{"scenario_id": ', encoding="utf-8")

            with self.assertRaises(ScenarioLoadError):
                load_scenario(path)

    def test_non_object_top_level_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "scenario_bad.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaises(ScenarioLoadError):
                load_scenario(path)


class ScenarioValidatorTests(unittest.TestCase):
    """Contract, scenario-rule, capacity, and connectivity tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = ScenarioValidator()
        cls.normal = load_scenario(NORMAL_PATH)
        cls.dry = load_scenario(DRY_PATH)
        cls.high = load_scenario(HIGH_PATH)
        cls.outage = load_scenario(OUTAGE_PATH)

    def test_valid_normal_scenario(self) -> None:
        report = self.validator.validate(
            self.normal,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.scenario_type, "NORMAL")
        self.assertEqual(
            report.capacity_check["remaining_capacity_ml_per_day"],
            100,
        )
        self.assertFalse(report.capacity_check["possible_infeasible"])

    def test_valid_dry_year_records_all_approved_changes(self) -> None:
        report = self.validator.validate(
            self.dry,
            reference=self.normal,
            scenario_type="DRY_YEAR",
        )

        self.assertTrue(report.valid, report.errors)

        changed_paths = {
            change["path"]
            for change in report.changes_from_reference
        }

        self.assertIn(
            "network.source_to_plant_links[0].maximum_flow_ml_per_day",
            changed_paths,
        )
        self.assertIn(
            "network.source_to_plant_links[1].maximum_flow_ml_per_day",
            changed_paths,
        )
        self.assertIn(
            "network.source_to_plant_links[2].maximum_flow_ml_per_day",
            changed_paths,
        )
        self.assertEqual(
            report.capacity_check["remaining_capacity_ml_per_day"],
            65,
        )

    def test_valid_high_demand_field_and_zero_margin(self) -> None:
        report = self.validator.validate(
            self.high,
            reference=self.normal,
            scenario_type="HIGH_DEMAND",
        )

        self.assertTrue(report.valid, report.errors)
        self.assertEqual(
            report.capacity_check["required_demand_ml_per_day"],
            600,
        )
        self.assertEqual(
            report.capacity_check["remaining_capacity_ml_per_day"],
            0,
        )
        self.assertFalse(report.capacity_check["possible_infeasible"])

    def test_valid_plant_outage_detects_capacity_and_connectivity_risk(self) -> None:
        report = self.validator.validate(
            self.outage,
            reference=self.normal,
            scenario_type="PLANT_OUTAGE",
        )

        self.assertTrue(report.valid, report.errors)
        self.assertEqual(
            report.capacity_check["active_plant_capacity_ml_per_day"],
            0,
        )
        self.assertTrue(report.capacity_check["possible_infeasible"])
        self.assertFalse(
            report.connectivity_check["all_required_zones_reachable"]
        )
        self.assertIn(
            "zone_1",
            report.connectivity_check["unreachable_zone_ids"],
        )

    def test_unknown_top_level_field_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["invented_field"] = 123

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "unknown field" in error.lower()
                for error in report.errors
            )
        )

    def test_unknown_nested_field_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["network"]["plants"][0]["unexpected"] = True

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "unexpected" in error
                for error in report.errors
            )
        )

    def test_missing_required_field_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        del scenario["network"]

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "network" in error
                for error in report.errors
            )
        )

    def test_wrong_type_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["network"]["demand_zones"][0][
            "demand_ml_per_day"
        ] = "500"

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "demand_ml_per_day" in error
                for error in report.errors
            )
        )

    def test_duplicate_source_id_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["sources"][1]["source_id"] = (
            scenario["sources"][0]["source_id"]
        )

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "duplicate source_id" in error.lower()
                for error in report.errors
            )
        )

    def test_unknown_link_source_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["network"]["source_to_plant_links"][0][
            "source_id"
        ] = "unknown_source"

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "unknown source" in error.lower()
                for error in report.errors
            )
        )

    def test_output_only_field_is_rejected(self) -> None:
        scenario = deepcopy(self.normal)
        scenario["objective"] = {"total_cost": 1}

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="NORMAL",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "output-only" in error.lower()
                for error in report.errors
            )
        )

    def test_dry_year_unapproved_demand_change_is_rejected(self) -> None:
        scenario = deepcopy(self.dry)
        scenario["network"]["demand_zones"][0][
            "demand_ml_per_day"
        ] = 510

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="DRY_YEAR",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "unapproved changes" in error.lower()
                for error in report.errors
            )
        )

    def test_high_demand_wrong_value_is_rejected(self) -> None:
        scenario = deepcopy(self.high)
        scenario["network"]["demand_zones"][0][
            "demand_ml_per_day"
        ] = 590

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="HIGH_DEMAND",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "must be 600" in error
                for error in report.errors
            )
        )

    def test_plant_outage_extra_change_is_rejected(self) -> None:
        scenario = deepcopy(self.outage)
        scenario["network"]["plants"][0][
            "maximum_processing_capacity_ml_per_day"
        ] = 0

        report = self.validator.validate(
            scenario,
            reference=self.normal,
            scenario_type="PLANT_OUTAGE",
        )

        self.assertFalse(report.valid)
        self.assertTrue(
            any(
                "unapproved changes" in error.lower()
                for error in report.errors
            )
        )

    def test_capacity_shortfall_is_warning_not_fake_solver_status(self) -> None:
        scenario = deepcopy(self.high)
        scenario["network"]["demand_zones"][0][
            "demand_ml_per_day"
        ] = 650

        capacity = self.validator.check_capacity(scenario)

        self.assertTrue(capacity["possible_infeasible"])
        self.assertLess(
            capacity["effective_capacity_ml_per_day"],
            capacity["required_demand_ml_per_day"],
        )

        serialised = json.dumps(capacity)

        self.assertNotIn("OPTIMAL", serialised)
        self.assertNotIn("INFEASIBLE", serialised)


if __name__ == "__main__":
    unittest.main(verbosity=2)
