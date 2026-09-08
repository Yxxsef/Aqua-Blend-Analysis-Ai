"""
DBSCAN: density-based spatial clustering of applications with noise.

Implemented natively against the formulation of Ester, Kriegel, Sander and
Xu (ref_32), because the definitions the method rests on -- core point,
directly density-reachable, density-connected -- are the content of the
write-up (Sect. sec:tech:dbscan) and following them is the point. The only
borrowed part is the radius neighbourhood query, which is an index, not
the algorithm.

Two properties make this the method of interest for the scenario path.
The number of clusters is a *result*: `eps` and `min_samples` are the
requests, so the k-selection procedure of Sect. 4.3 does not apply to it
and the density parameters are swept instead. And an observation may be
left unassigned. Nothing else in the package can say "this operating
state is too rare to be a regime" -- a method that assigns everything
hands the optimisation team a regime that is really a handful of upset
conditions averaged together.

What this module does *not* decide is whether a noise observation becomes
a scenario. It reports the noise and where it came from; the decision is
the scenario task's (ref_18 makes the same separation for temporal
segmentation of consumption data).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.neighbors import NearestNeighbors

from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import (
    NOISE_LABEL,
    ArrayLike,
    Assignment,
    Backend,
    Family,
    MatrixLike,
    MetricLike,
    Scaling,
    SubFamily,
)
from ....core.validation import ensure_fitted
from .base import BaseDensityClusterer


@register("dbscan")
class DBSCAN(BaseDensityClusterer):
    """Clusters as maximal sets of density-connected points.

    A point is a *core point* when at least `min_samples` observations,
    itself included, lie within `eps` of it. Clusters grow from core
    points by density-reachability; a non-core point inside the radius of
    one joins it as a *border point*; anything reached by nothing is
    noise, labelled -1.

    Parameters
    ----------
    eps
        Radius of the neighbourhood. The parameter the result is most
        sensitive to, and the one with no default worth trusting: it is a
        distance in the units of the (scaled) features, so it has to be
        chosen against the data. See the write-up for the k-distance
        procedure of ref_33.
    min_samples
        How many neighbours, counting the point itself, make a point a
        core point. Read as the smallest group the analyst is willing to
        call a regime rather than a rare state.
    metric
        Measure defining the neighbourhood, or "precomputed" to pass an
        (m, m) dissimilarity matrix as `X`.
    n_jobs
        Parallelism for the neighbour search, which dominates the cost.

    Fitted attributes
    -----------------
    labels_ : ndarray of shape (m,)
        Cluster index per observation; -1 for noise.
    core_sample_indices_ : ndarray
        Positions of the core points.
    n_neighbours_ : ndarray of shape (m,)
        Neighbours within `eps`, counting the point itself. The density
        estimate the clusters were formed from, kept because it is what a
        diagnostic plots when a result looks wrong.
    n_clusters_, n_noise_ : int
        Both results, never requests; recounted from `labels_` by the
        family base.

    Notes
    -----
    Deterministic given the data, with one caveat worth stating: a border
    point inside the radius of two clusters joins whichever reaches it
    first, so its label depends on the order observations arrive in, not
    on the data alone. The expansion below scans in index order, which
    fixes the outcome for a fixed input and matches the reference
    implementations.
    """

    _capabilities = Capabilities(
        family=Family.PARTITIONAL,
        subfamily=SubFamily.DENSITY_BASED,
        backend=Backend.NATIVE,
        assignment=Assignment.CRISP,
        # An agglomeration of density-connected points, defined only over
        # the sample it was fitted on: there is no rule assigning an
        # unseen observation without recomputing the connectivity.
        is_inductive=False,
        produces_hierarchy=False,
        supports_precomputed=True,
        # `eps` and `min_samples` are the requests; |C| falls out.
        requires_n_clusters=False,
        handles_noise=True,
        handles_missing=False,
        handles_categorical=False,
        # `eps` is a distance in feature units, so rescaling a column
        # changes which points are neighbours. This is the declaration
        # that justifies the scaling step of Sect. 3.3.
        scale_invariant=False,
        deterministic=True,
        scales_to=Scaling.MEDIUM,
        time_complexity="O(m log m) with a spatial index; O(m^2) without",
        space_complexity="O(m k) for the neighbourhoods, k the mean degree",
        references=("ref_32", "ref_33", "ref_18", "ref_1"),
        doc_label="sec:tech:dbscan",
    )

    #: Added to the family's. `core_sample_indices_` is not required by
    #: `BaseDensityClusterer` -- not every density method has core points
    #: -- but this one does, and Sect. 8.1 reports the count.
    _required_fitted = ("labels_", "core_sample_indices_", "n_neighbours_")

    def __init__(
        self,
        eps: float = 0.5,
        *,
        min_samples: int = 5,
        metric: MetricLike = "euclidean",
        n_jobs: int | None = None,
    ) -> None:
        super().__init__(min_samples=min_samples, metric=metric, n_jobs=n_jobs)
        self.eps = eps

    def _validate_params(self) -> None:
        """Refuse parameters for which the definitions do not hold.

        Checked here rather than in `__init__`, per the contract, so the
        parameters round-trip through `get_params`/`set_params` unchanged.

        A non-positive `eps` gives every point an empty neighbourhood and
        labels the whole sample noise; a `min_samples` below one makes
        every point a core point and the partition meaningless. Both are
        results a caller would read as a finding, so both raise.
        """
        super()._validate_params()

        if not isinstance(self.eps, (int, float)) or self.eps <= 0:
            raise ValueError(
                f"eps must be a positive distance; got {self.eps!r}. It is "
                f"the radius of the neighbourhood, in the units of the "
                f"features as they reach the method, so it has to be chosen "
                f"against the scaled data rather than left at a default."
            )
        if not isinstance(self.min_samples, (int, np.integer)) or self.min_samples < 1:
            raise ValueError(
                f"min_samples must be an integer of at least 1; got "
                f"{self.min_samples!r}. It counts the point itself, so 1 "
                f"makes every observation a core point."
            )

    def _density_estimate(self, X: MatrixLike) -> ArrayLike:
        """Return the neighbour count within `eps` for each observation.

        The density quantity this method is defined on: |N_eps(p)|,
        counting p itself, which is what `min_samples` is compared
        against. The neighbourhoods themselves are cached privately for
        the expansion below, so the radius query runs once per fit rather
        than once per step.
        """
        index = NearestNeighbors(
            radius=self.eps,
            metric=self.metric,
            n_jobs=self.n_jobs,
        ).fit(X)

        # Sorted so the expansion visits neighbours in a fixed order, which
        # is what makes a border point's cluster reproducible.
        neighbourhoods = index.radius_neighbors(X, return_distance=False)
        self._neighbourhoods = [np.sort(np.asarray(n, dtype=int)) for n in neighbourhoods]

        return np.array([n.size for n in self._neighbourhoods], dtype=int)

    def _extract_clusters(self, X: MatrixLike, density: ArrayLike) -> None:
        """Grow clusters from core points by density-reachability.

        The three definitions of ref_32, in order: a core point is one
        whose neighbourhood reaches `min_samples`; a point is directly
        density-reachable from a core point in whose radius it lies; a
        cluster is a maximal set of points density-connected through
        chains of the former.

        Border points are assigned but not expanded from -- the test that
        the chain only continues through core points is what stops two
        clusters joined by a thin bridge of border points from merging.

        Sets `labels_` only; `n_clusters_` and `n_noise_` are recounted
        from them by the family base, which also enforces the -1
        convention.
        """
        counts = np.asarray(density, dtype=int)
        is_core = counts >= self.min_samples

        labels = np.full(counts.shape[0], NOISE_LABEL, dtype=int)
        cluster = 0

        for start in range(labels.shape[0]):
            # Already in a cluster, or not a seed: a border point never
            # starts one, which is what keeps a cluster's identity with
            # its dense interior.
            if labels[start] != NOISE_LABEL or not is_core[start]:
                continue

            stack = [start]
            while stack:
                point = stack.pop()
                if labels[point] != NOISE_LABEL:
                    continue
                labels[point] = cluster
                if is_core[point]:
                    # Only a core point extends the chain.
                    for neighbour in self._neighbourhoods[point]:
                        if labels[neighbour] == NOISE_LABEL:
                            stack.append(int(neighbour))
            cluster += 1

        self.labels_ = labels
        self.core_sample_indices_ = np.flatnonzero(is_core)
        self.n_neighbours_ = counts

    def noise_report(self, timestamps: Any = None) -> Any:
        """Return the noise observations, with when they occurred.

        A rare state the operations team can be asked about is one with a
        timestamp; a row index on its own is not something anyone can
        investigate. `timestamps` takes the dataset's "time" column, or
        any per-observation label; without one the report still names the
        positions, so the method is usable on data that carries no clock.

        `n_neighbours_` travels with each row because it says *how* far
        from dense a point was: a noise observation one neighbour short of
        the threshold is a different finding from one that is entirely
        alone, and the second is the one worth asking about.

        This reports; it does not decide. Whether these become a
        rare-event scenario or are dropped is the scenario task's call,
        and it has to be recorded there.
        """
        import pandas as pd

        ensure_fitted(self, "labels_")
        positions = np.flatnonzero(self.noise_mask())

        report = pd.DataFrame(
            {
                "position": positions,
                "n_neighbours": np.asarray(self.n_neighbours_)[positions],
                "short_by": self.min_samples - np.asarray(self.n_neighbours_)[positions],
            }
        )
        if timestamps is not None:
            stamps = np.asarray(timestamps)
            if stamps.shape[0] != self.labels_.shape[0]:
                raise ValueError(
                    f"timestamps has {stamps.shape[0]} entries but the fit "
                    f"labelled {self.labels_.shape[0]} observations; the two "
                    f"must line up or a noise point is traced to the wrong "
                    f"period."
                )
            report.insert(1, "when", stamps[positions])
        return report
