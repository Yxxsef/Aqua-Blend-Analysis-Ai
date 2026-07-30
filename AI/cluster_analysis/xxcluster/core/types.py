"""
Shared type aliases and enumerations.

Every module imports its vocabulary from here so that a symbol means the
same thing in a clustering method, a validity index and a report. Add a
new alias here rather than restating a structural type inline.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Mapping, Sequence, TypeAlias, Union

import numpy as np

# --- Data -----------------------------------------------------------------
# Anything convertible to a 2-D float array of shape (n_samples, n_features).
# `n` and `d` follow the notation table: n observations, d features.
MatrixLike: TypeAlias = Any
ArrayLike: TypeAlias = Any

#: Square (n, n) matrix of pairwise dissimilarities, d(x_i, x_j).
DissimilarityMatrix: TypeAlias = np.ndarray

#: Crisp cluster assignment, shape (n,), dtype int. Noise is -1 by convention.
Labels: TypeAlias = np.ndarray

#: Soft assignment, shape (n, |C|), rows summing to 1 for probabilistic models.
Memberships: TypeAlias = np.ndarray

#: Low-dimensional representation, shape (n, n_components).
Embedding: TypeAlias = np.ndarray

#: SciPy-format linkage matrix, shape (n - 1, 4).
LinkageMatrix: TypeAlias = np.ndarray

# --- Parameters -----------------------------------------------------------
Seed: TypeAlias = Union[int, np.random.Generator, np.random.RandomState, None]

#: Either a named metric resolved by the backend, or a callable d(x, y).
MetricLike: TypeAlias = Union[str, Callable[[ArrayLike, ArrayLike], float]]

#: Hyperparameter grid in scikit-learn's `param_grid` form.
ParamGrid: TypeAlias = Mapping[str, Sequence[Any]]

#: Metric name -> value, as emitted by the evaluation layer.
ScoreDict: TypeAlias = Mapping[str, float]


class ComponentKind(str, Enum):
    """Role a component plays, used to partition the registry.

    Extending horizontally means adding a member here and a matching base
    class in `xxcluster.core.base`.
    """

    CLUSTERER = "clusterer"
    DIM_REDUCER = "dim_reducer"
    DISSIMILARITY = "dissimilarity"
    VALIDITY_INDEX = "validity_index"
    SELECTOR = "selector"
    TRANSFORMER = "transformer"
    OUTLIER_DETECTOR = "outlier_detector"
    GENERATOR = "generator"
    PREDICTOR = "predictor"
    TASK = "task"


class Family(str, Enum):
    """Clustering families, mirroring Sect. 2.2 of the documentation."""

    HIERARCHICAL = "hierarchical"
    PARTITIONAL = "partitional"
    HYBRID = "hybrid"


class SubFamily(str, Enum):
    """Second-level taxonomy, mirroring the subsection layout of Sect. 7.

    Hierarchical splits by construction direction; partitional splits by
    the strategy used to optimise the criterion function.
    """

    # Hierarchical
    AGGLOMERATIVE = "agglomerative"
    DIVISIVE = "divisive"
    # Partitional
    SSE_BASED = "sse_based"
    DENSITY_BASED = "density_based"
    MODEL_BASED = "model_based"
    GRAPH_THEORETIC = "graph_theoretic"
    SUBSPACE = "subspace"
    SEARCH_BASED = "search_based"
    FUZZY = "fuzzy"
    MISCELLANEOUS = "miscellaneous"


class Assignment(str, Enum):
    """How a method assigns an observation to a cluster."""

    CRISP = "crisp"
    FUZZY = "fuzzy"
    PROBABILISTIC = "probabilistic"


class Backend(str, Enum):
    """Where the fitting logic actually lives.

    NATIVE means implemented in this package against the formulation in the
    documentation; the others mean the class adapts a third-party estimator.
    """

    NATIVE = "native"
    SKLEARN = "sklearn"
    SCIPY = "scipy"
    THIRD_PARTY = "third_party"


class Scaling(str, Enum):
    """Order-of-magnitude guide to the data size a method tolerates.

    Set from the complexity paragraph of the method's documentation
    section, not measured.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
