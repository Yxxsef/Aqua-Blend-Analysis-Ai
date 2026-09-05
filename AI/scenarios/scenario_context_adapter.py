from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return default

    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _to_mapping(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact(value: Any) -> Any:
    if is_dataclass(value):
        return _compact(asdict(value))
    if isinstance(value, list):
        return [_compact(item) for item in value]
    if isinstance(value, dict):
        return {k: _compact(v) for k, v in value.items() if v is not None}
    return value


@dataclass(slots=True)
class SourceContext:
    source_id: str
    name: str | None = None
    enabled: bool | None = None
    forced_inactive: bool | None = None
    minimum_withdrawal_ml_per_day: float | None = None
    maximum_withdrawal_ml_per_day: float | None = None
    withdrawal_bounds_override: dict[str, Any] = field(default_factory=dict)
    availability_status: str | None = None


@dataclass(slots=True)
class PlantContext:
    plant_id: str
    name: str | None = None
    enabled: bool | None = None
    minimum_processing_capacity_ml_per_day: float | None = None
    maximum_processing_capacity_ml_per_day: float | None = None
    capacity_override: dict[str, Any] = field(default_factory=dict)
    availability_status: str | None = None


@dataclass(slots=True)
class DemandZoneContext:
    zone_id: str
    name: str | None = None
    demand_ml_per_day: float | None = None


@dataclass(slots=True)
class SourcePlantLinkContext:
    source_id: str | None = None
    plant_id: str | None = None
    enabled: bool | None = None
    maximum_flow_ml_per_day: float | None = None
    override: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlantZoneLinkContext:
    plant_id: str | None = None
    zone_id: str | None = None
    enabled: bool | None = None
    maximum_flow_ml_per_day: float | None = None
    override: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QualityLimitContext:
    parameter_id: str
    name: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    profile_id: str | None = None
    override: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioAIContext:
    scenario_context_version: str
    scenario_id: str | None
    run_id: str | None = None
    scenario_name: str | None = None
    description: str | None = None
    status: str | None = None
    is_ready: bool | None = None
    validation_issues: list[str] = field(default_factory=list)
    sources: list[SourceContext] = field(default_factory=list)
    plants: list[PlantContext] = field(default_factory=list)
    demand_zones: list[DemandZoneContext] = field(default_factory=list)
    source_to_plant_links: list[SourcePlantLinkContext] = field(default_factory=list)
    plant_to_zone_links: list[PlantZoneLinkContext] = field(default_factory=list)
    quality_limits: list[QualityLimitContext] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _compact(asdict(self))


class ScenarioContextAdapter:
    VERSION = "1.0"

    def build(self, scenario_data: Any, run_id: str | None = None) -> ScenarioAIContext:
        data = _to_mapping(scenario_data)

        context = ScenarioAIContext(
            scenario_context_version=self.VERSION,
            scenario_id=_as_str(_get(data, "scenario_id")),
            run_id=_as_str(run_id) or _as_str(_get(data, "run_id")),
            scenario_name=_as_str(_get(data, "scenario_name", "name")),
            description=_as_str(_get(data, "description")),
            status=_as_str(_get(data, "status")),
            is_ready=_as_bool(_get(data, "is_ready")),
            validation_issues=self._string_list(_get(data, "validation_issues")),
            sources=self._build_sources(_get(data, "sources")),
            plants=self._build_plants(_get(data, "plants")),
            demand_zones=self._build_demand_zones(_get(data, "demand_zones")),
            source_to_plant_links=self._build_source_plant_links(
                _get(data, "source_to_plant_links")
            ),
            plant_to_zone_links=self._build_plant_zone_links(
                _get(data, "plant_to_zone_links")
            ),
            quality_limits=self._build_quality_limits(
                _get(data, "quality_limits"), data
            ),
        )
        return context

    def _build_sources(self, items: Any) -> list[SourceContext]:
        result: list[SourceContext] = []
        for item in _as_list(items):
            row = _to_mapping(item)
            source_id = _as_str(_get(row, "source_id", "id"))
            if not source_id:
                continue

            result.append(
                SourceContext(
                    source_id=source_id,
                    name=_as_str(_get(row, "name")),
                    enabled=_as_bool(_get(row, "enabled")),
                    forced_inactive=_as_bool(_get(row, "forced_inactive")),
                    minimum_withdrawal_ml_per_day=_as_float(
                        _get(row, "minimum_withdrawal_ml_per_day")
                    ),
                    maximum_withdrawal_ml_per_day=_as_float(
                        _get(row, "maximum_withdrawal_ml_per_day")
                    ),
                    withdrawal_bounds_override=_compact(
                        _get(row, "withdrawal_bounds_override", "override", default={})
                    )
                    or {},
                    availability_status=_as_str(_get(row, "availability_status")),
                )
            )
        return result

    def _build_plants(self, items: Any) -> list[PlantContext]:
        result: list[PlantContext] = []
        for item in _as_list(items):
            row = _to_mapping(item)
            plant_id = _as_str(_get(row, "plant_id", "id"))
            if not plant_id:
                continue

            result.append(
                PlantContext(
                    plant_id=plant_id,
                    name=_as_str(_get(row, "name")),
                    enabled=_as_bool(_get(row, "enabled")),
                    minimum_processing_capacity_ml_per_day=_as_float(
                        _get(row, "minimum_processing_capacity_ml_per_day")
                    ),
                    maximum_processing_capacity_ml_per_day=_as_float(
                        _get(row, "maximum_processing_capacity_ml_per_day")
                    ),
                    capacity_override=_compact(
                        _get(row, "capacity_override", "override", default={})
                    )
                    or {},
                    availability_status=_as_str(_get(row, "availability_status")),
                )
            )
        return result

    def _build_demand_zones(self, items: Any) -> list[DemandZoneContext]:
        result: list[DemandZoneContext] = []
        for item in _as_list(items):
            row = _to_mapping(item)
            zone_id = _as_str(_get(row, "zone_id", "demand_zone_id", "id"))
            if not zone_id:
                continue

            result.append(
                DemandZoneContext(
                    zone_id=zone_id,
                    name=_as_str(_get(row, "name")),
                    demand_ml_per_day=_as_float(_get(row, "demand_ml_per_day")),
                )
            )
        return result

    def _build_source_plant_links(self, items: Any) -> list[SourcePlantLinkContext]:
        result: list[SourcePlantLinkContext] = []
        for item in _as_list(items):
            row = _to_mapping(item)
            source_id = _as_str(_get(row, "source_id"))
            plant_id = _as_str(_get(row, "plant_id"))
            if not source_id and not plant_id:
                continue

            result.append(
                SourcePlantLinkContext(
                    source_id=source_id,
                    plant_id=plant_id,
                    enabled=_as_bool(_get(row, "enabled")),
                    maximum_flow_ml_per_day=_as_float(
                        _get(row, "maximum_flow_ml_per_day")
                    ),
                    override=_compact(_get(row, "override", default={})) or {},
                )
            )
        return result

    def _build_plant_zone_links(self, items: Any) -> list[PlantZoneLinkContext]:
        result: list[PlantZoneLinkContext] = []
        for item in _as_list(items):
            row = _to_mapping(item)
            plant_id = _as_str(_get(row, "plant_id"))
            zone_id = _as_str(_get(row, "zone_id"))
            if not plant_id and not zone_id:
                continue

            result.append(
                PlantZoneLinkContext(
                    plant_id=plant_id,
                    zone_id=zone_id,
                    enabled=_as_bool(_get(row, "enabled")),
                    maximum_flow_ml_per_day=_as_float(
                        _get(row, "maximum_flow_ml_per_day")
                    ),
                    override=_compact(_get(row, "override", default={})) or {},
                )
            )
        return result

    def _build_quality_limits(self, quality_limits: Any, data: dict[str, Any]) -> list[QualityLimitContext]:
        result: list[QualityLimitContext] = []
        for item in _as_list(quality_limits):
            row = _to_mapping(item)
            parameter_id = _as_str(_get(row, "parameter_id", "quality_parameter_id", "id"))
            if not parameter_id:
                continue

            result.append(
                QualityLimitContext(
                    parameter_id=parameter_id,
                    name=_as_str(_get(row, "name")),
                    minimum=_as_float(_get(row, "minimum")),
                    maximum=_as_float(_get(row, "maximum")),
                    unit=_as_str(_get(row, "unit")),
                    profile_id=_as_str(_get(row, "profile_id", "quality_profile_id"))
                    or _as_str(_get(data, "quality_profile_id")),
                    override=_compact(_get(row, "override", default={})) or {},
                )
            )
        return result

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        return [
            item
            for item in (_as_str(v) for v in _as_list(value))
            if item is not None
        ]