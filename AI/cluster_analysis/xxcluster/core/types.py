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
# Anything convertible to a 2-D float array of shape (m, n).
# Symbols follow the notation table: m observations, n features. Note that
# scikit-learn calls the same axes (n_samples, n_features), so its parameter
# and attribute names -- `n_samples`, `n_features_in_` -- keep that spelling
# and are not renamed here.
MatrixLike: TypeAlias = Any
ArrayLike: TypeAlias = Any

#: Square (m, m) matrix of pairwise dissimilarities, d(x_i, x_j).
DissimilarityMatrix: TypeAlias = np.ndarray

#: Crisp cluster assignment, shape (m,), dtype int. Noise is -1 by convention.
Labels: TypeAlias = np.ndarray

#: The label reserved for an observation no method assigned. Defined here so
#: the validation helpers and `mixins.NoiseAwareMixin` share one constant --
#: two spellings of this convention is how a noise point becomes cluster 0.
NOISE_LABEL: int = -1

#: Soft assignment, shape (m, |C|), rows summing to 1 for probabilistic models.
Memberships: TypeAlias = np.ndarray

#: Low-dimensional representation, shape (m, n_components).
Embedding: TypeAlias = np.ndarray

#: SciPy-format linkage matrix, shape (m - 1, 4).
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


class PrecomputedKind(str, Enum):
    """What kind of square matrix a component accepts as precomputed input.

    Three kinds, because they obey different rules and confusing them
    produces a wrong result rather than an error. A method declares one;
    `PrecomputedMixin` validates against it.

    DISSIMILARITY
        d(x, y). Zero diagonal, non-negative. Symmetry optional --
        Def. 2 permits a measure that is not a metric.
    AFFINITY
        Edge weights of a similarity graph. Non-negative and symmetric;
        the diagonal is unconstrained. Negative weights would make the
        graph Laplacian meaningless.
    KERNEL
        k(x, y) = <phi(x), phi(y)>. Symmetric with a non-negative
        diagonal, but off-diagonal entries may be negative -- a linear
        kernel on centred data routinely is.
    """

    DISSIMILARITY = "dissimilarity"
    AFFINITY = "affinity"
    KERNEL = "kernel"


class Scaling(str, Enum):
    """Order-of-magnitude guide to the data size a method tolerates.

    Set from the complexity paragraph of the method's documentation
    section, not measured.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
