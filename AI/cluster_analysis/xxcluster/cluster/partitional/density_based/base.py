"""
Base class for density-based methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from ....core.base import BaseClusterer
from ....core.mixins import NoiseAwareMixin, PrecomputedMixin
from ....core.types import NOISE_LABEL, ArrayLike, MatrixLike, MetricLike
from ....core.validation import check_labels, ensure_fitted


class BaseDensityClusterer(NoiseAwareMixin, PrecomputedMixin, BaseClusterer, ABC):
    """A method that recovers clusters as connected dense regions.

    Derives from `BaseClusterer` rather than `BasePartitionalClusterer`:
    these methods are placed in the partitional family by Sect. 2.2, but
    they neither iterate to convergence nor depend on an initialisation, so
    the iterative-relocation parameters would be dead weight.

    The number of clusters is a result, never a request, which is what
    makes the family attractive here and also what makes it harder to
    compare: two parameter settings give different `n_clusters_`, so the
    k-selection procedure of Sect. 4.3 does not apply and the density
    parameters must be swept instead.

    Parameters
    ----------
    min_samples
        Density threshold: how many neighbours make a point a core point.
    metric
        Measure defining the neighbourhood, or "precomputed".
    n_jobs
        Parallelism for the neighbour search, which dominates the cost.

    Fitted attributes
    -----------------
    core_sample_indices_ : ndarray
        Observations identified as core points.
    n_noise_ : int
        Observations labelled -1; see `NoiseAwareMixin`.
    """

    #: Added to `BaseClusterer`'s declaration. `n_noise_` is what
    #: distinguishes this family's result from a partition in the strict
    #: sense of Def. 2, and Sect. 8.1 reports it as a column, so a method
    #: that leaves it unset is not reportable. Derived from `labels_` below
    #: when `_extract_clusters` does not set it itself.
    #:
    #: `core_sample_indices_` is deliberately not required: not every
    #: density method has core points in the DBSCAN sense.
    _required_fitted = ("n_noise_",)

    core_sample_indices_: ArrayLike

    def __init__(
        self,
        *,
        min_samples: int = 5,
        metric: MetricLike = "euclidean",
        n_jobs: int | None = None,
    ) -> None:
        self.min_samples = min_samples
        self.metric = metric
        self.n_jobs = n_jobs

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Estimate density, extract clusters, and mark the remainder noise.

        Concrete for the whole family, and thin by design: the two steps
        are the family's shape, and everything that varies between methods
        lives in them. A native method writes `_density_estimate` and
        `_extract_clusters` and nothing else.

        The density estimate is passed to the extraction rather than
        recomputed inside it, so the quantity a diagnostic plots is exactly
        the quantity the clusters were formed from.
        """
        density = self._density_estimate(X)
        self._extract_clusters(X, density)
        self._derive_noise()

    def _derive_noise(self) -> None:
        """Recount the clusters and the noise from `labels_`.

        Both are functions of the labels, so they are recomputed rather than
        filled in when absent: a value left over from an earlier fit of the
        same instance would otherwise survive and be reported.

        Validating the labels here also enforces the convention at the point
        it is established. A method that marks noise as `0` instead of `-1`
        produces a plausible partition with a phantom cluster, and nothing
        downstream could tell.
        """
        ensure_fitted(self, "labels_")
        labels = check_labels(self.labels_)
        self.labels_ = labels

        assigned = labels[labels != NOISE_LABEL]
        self.n_clusters_ = int(np.unique(assigned).size)
        self.n_noise_ = int(np.sum(labels == NOISE_LABEL))

    def _density_estimate(self, X: MatrixLike) -> ArrayLike:
        """Return the per-observation density quantity the method uses.

        A neighbour count within a radius, a core distance, or a mutual
        reachability -- whichever the method defines. Exposed separately
        because it is worth plotting when diagnosing a poor result.

        Required of a native method; an adapted one never reaches it.
        """
        raise NotImplementedError

    def _extract_clusters(self, X: MatrixLike, density: ArrayLike) -> None:
        """Form clusters from the density estimate and label the remainder.

        Must set `labels_`, `n_clusters_`, `n_noise_` and
        `core_sample_indices_`. The step where the family's variants
        differ -- a fixed radius, a hierarchy of densities, a stability
        criterion over that hierarchy.

        Required of a native method; an adapted one never reaches it.
        """
        raise NotImplementedError
