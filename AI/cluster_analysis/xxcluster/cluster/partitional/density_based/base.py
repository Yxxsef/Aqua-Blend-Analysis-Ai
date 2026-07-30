"""
Base class for density-based methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ....core.base import BaseClusterer
from ....core.mixins import NoiseAwareMixin, PrecomputedMixin
from ....core.types import ArrayLike, MatrixLike, MetricLike


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
        """Estimate density, extract clusters, and mark the remainder noise."""
        raise NotImplementedError

    @abstractmethod
    def _density_estimate(self, X: MatrixLike) -> ArrayLike:
        """Return the per-observation density quantity the method uses.

        A neighbour count within a radius, a core distance, or a mutual
        reachability -- whichever the method defines. Exposed separately
        because it is worth plotting when diagnosing a poor result.
        """
        ...

    @abstractmethod
    def _extract_clusters(self, X: MatrixLike, density: ArrayLike) -> None:
        """Form clusters from the density estimate and label the remainder.

        Must set `labels_`, `n_clusters_`, `n_noise_` and
        `core_sample_indices_`. The step where the family's variants
        differ -- a fixed radius, a hierarchy of densities, a stability
        criterion over that hierarchy.
        """
        ...
