"""
The contract layer.

Nothing in `core` is specific to clustering, or to AquaBlend. It holds the
abstract classes, mixins, protocols, tags, registry and validation that
every other subpackage depends on, and it depends on none of them. Any
import from `core` into a sibling subpackage is a design error.

Import contracts from here rather than from the module that defines them,
so internal reorganisation stays internal.
"""

from __future__ import annotations

from .adapters import AdaptedClusterer, AdaptedDimReducer, BackendAdapter
from .base import (
    BaseClusterer,
    BaseComponent,
    BaseDimReducer,
    BaseGenerator,
    BaseOutlierDetector,
    BasePredictor,
    BaseTransformer,
)
from .exceptions import (
    BackendUnavailableError,
    ContractViolationError,
    ConvergenceError,
    NotFittedError,
    RegistryError,
    XXClusterError,
)
from .mixins import (
    HierarchyMixin,
    InductiveMixin,
    NoiseAwareMixin,
    PersistableMixin,
    PrecomputedMixin,
    ProbabilisticMixin,
    SoftAssignmentMixin,
)
from .registry import REGISTRY, ComponentRegistry, register
from .tags import Capabilities
from .types import (
    Assignment,
    Backend,
    ComponentKind,
    Family,
    PrecomputedKind,
    Scaling,
    SubFamily,
)
from .validation import (
    check_affinity_matrix,
    check_dissimilarity_matrix,
    check_kernel_matrix,
)

__all__ = [
    # Base classes
    "BaseComponent",
    "BaseClusterer",
    "BaseDimReducer",
    "BaseTransformer",
    "BaseOutlierDetector",
    "BaseGenerator",
    "BasePredictor",
    # Adapters
    "BackendAdapter",
    "AdaptedClusterer",
    "AdaptedDimReducer",
    # Mixins
    "InductiveMixin",
    "SoftAssignmentMixin",
    "HierarchyMixin",
    "NoiseAwareMixin",
    "ProbabilisticMixin",
    "PrecomputedMixin",
    "PersistableMixin",
    # Declarations and registry
    "Capabilities",
    "REGISTRY",
    "ComponentRegistry",
    "register",
    # Enumerations
    "Assignment",
    "Backend",
    "ComponentKind",
    "Family",
    "PrecomputedKind",
    "Scaling",
    "SubFamily",
    # Validation
    "check_dissimilarity_matrix",
    "check_affinity_matrix",
    "check_kernel_matrix",
    # Errors
    "XXClusterError",
    "ContractViolationError",
    "BackendUnavailableError",
    "ConvergenceError",
    "RegistryError",
    "NotFittedError",
]
