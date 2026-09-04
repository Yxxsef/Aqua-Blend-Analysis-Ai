"""
Base class shared by hierarchical methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import fcluster

from ...core.base import BaseClusterer
from ...core.exceptions import ContractViolationError
from ...core.mixins import HierarchyMixin, PrecomputedMixin
from ...core.types import Labels, LinkageMatrix, MatrixLike, MetricLike
from ...core.validation import check_n_clusters, ensure_fitted
from .linkage import check_linkage_metric

#: Tolerance on the monotonicity check; a tree is non-monotonic only where a
#: merge height falls by more than a floating-point wobble.
_TOL = 1e-9


class BaseHierarchicalClusterer(HierarchyMixin, PrecomputedMixin, BaseClusterer, ABC):
    """A clustering method that builds a hierarchy over the sample.

    Fitting produces the full tree; `n_clusters` is therefore a cut level
    rather than a fitting parameter, and `labels_` is the partition at the
    requested level. Leaving both `n_clusters` and `distance_threshold`
    unset is valid: the tree is built and no cut is applied until `cut` is
    called.

    Both construction directions consume a dissimilarity and a linkage
    criterion, so both are declared here. `metric="precomputed"` accepts a
    dissimilarity matrix directly, which is how a custom measure from
    `xxcluster.measures.dissimilarity` reaches this family.

    Parameters
    ----------
    n_clusters
        Cut level applied after fitting, if any.
    metric
        Name of a measure, a callable, or "precomputed".
    linkage
        Name of a criterion registered in `linkage.py`.
    distance_threshold
        Cut height, as an alternative to `n_clusters`. Mutually exclusive
        with it.

    Fitted attributes
    -----------------
    linkage_, children_
        The hierarchy; see `HierarchyMixin`.
    distances_ : ndarray of shape (m - 1,)
        Merge or split height at each step, for the dendrogram.
    """

    #: The tree itself, in both formats. Declared rather than only
    #: documented, so `_check_fitted` catches a `_build_hierarchy` that
    #: produced no tree, and so `BackendAdapter._collect_fitted` copies them
    #: from a backend. `_complete_hierarchy` derives whichever of the three
    #: were not set, so a method supplies only the format it naturally has.
    _required_fitted = ("linkage_", "children_", "distances_")

    distances_: Any

    def __init__(
        self,
        n_clusters: int | None = None,
        *,
        metric: MetricLike = "euclidean",
        linkage: str = "ward",
        distance_threshold: float | None = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.metric = metric
        self.linkage = linkage
        self.distance_threshold = distance_threshold

    def _validate_params(self) -> None:
        """Resolve the linkage criterion and refuse a metric it is not defined for.

        A step of the `fit` template, so it runs before the input is
        validated and before any tree is built -- and on the adapted path
        as well as the native one, since `AdaptedClusterer` overrides
        `_fit`, not `fit`. That matters here: Ward's Euclidean requirement
        must hold for a method whose backend builds the tree just as much
        as for one that builds it itself.

        `requires_euclidean` was a declaration nothing read until this
        override; `linkage.check_linkage_metric` is where the rule it
        states is now applied. Resolving the name here also turns an
        unregistered `linkage=` into an error at the top of `fit` rather
        than at the first merge.
        """
        super()._validate_params()
        check_linkage_metric(self.linkage, self.metric)

    def cut(
        self, n_clusters: int | None = None, threshold: float | None = None
    ) -> Labels:
        """Return the partition obtained by cutting the fitted hierarchy.

        Concrete for the whole family: cutting a linkage matrix does not
        depend on how the matrix was built. This is the practical value of
        HCA per Sect. 2.2 -- one fit yields every partition, so sweeping the
        cut level costs no refitting.

        Exactly one of `n_clusters` and `threshold` is given. Both together
        are refused rather than silently prioritised, because the two
        express different intents and a caller who supplied both has not
        decided which.

        Labels are returned zero-based with SciPy's one-based output shifted
        down, so a cut agrees with `labels_` and with every consumer of the
        package's label convention.
        """
        ensure_fitted(self, "linkage_")

        if n_clusters is not None and threshold is not None:
            raise ValueError(
                "cut accepts n_clusters or threshold, not both: a level and a "
                "height are different requests and they need not agree."
            )
        if n_clusters is None and threshold is None:
            raise ValueError(
                "cut needs either n_clusters or threshold; with neither there "
                "is no cut to apply."
            )

        Z = np.asarray(self.linkage_, dtype=float)
        if n_clusters is not None:
            requested = check_n_clusters(n_clusters, n_samples=Z.shape[0] + 1)
            labels = fcluster(Z, t=requested, criterion="maxclust")
        else:
            self._check_monotonic(Z)
            labels = fcluster(Z, t=float(threshold), criterion="distance")
        return (np.asarray(labels, dtype=int) - 1).astype(int)

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the hierarchy, then apply the requested cut, if any.

        Concrete for the whole family; a native method writes only
        `_build_hierarchy`. The order matters: the tree is built once and
        the cut is read off it, so `n_clusters` costs nothing at fit time
        and can be changed afterwards through `cut`.
        """
        if self.n_clusters is not None and self.distance_threshold is not None:
            raise ValueError(
                "n_clusters and distance_threshold are mutually exclusive; "
                "both were given, and they need not select the same partition."
            )

        # Dropped before rebuilding so that a refit on different data cannot
        # inherit the previous tree through the derivation below.
        for name in self._required_fitted:
            if hasattr(self, name):
                delattr(self, name)

        self._build_hierarchy(X)
        self._complete_hierarchy()

        if self.n_clusters is not None:
            self.labels_ = self.cut(n_clusters=self.n_clusters)
        elif self.distance_threshold is not None:
            self.labels_ = self.cut(threshold=self.distance_threshold)
        else:
            # No cut requested, which the contract permits. The uncut
            # hierarchy is its own leaves, so every observation is its own
            # cluster until `cut` is called.
            self.labels_ = np.arange(np.asarray(self.linkage_).shape[0] + 1)

        self.n_clusters_ = int(np.unique(self.labels_).size)

    def _complete_hierarchy(self) -> None:
        """Derive whichever of the three tree attributes were not set.

        `linkage_` is SciPy's format and `children_` scikit-learn's; the two
        are consumed by different tools and neither is reconstructible from
        nothing, but each is reconstructible from the other. Deriving here
        means a native method sets the one its construction produces, and an
        adapted method whose backend reports only `children_` and
        `distances_` still satisfies `HierarchyMixin`.

        An adapter should call this from `_derive_missing`, since
        `AdaptedClusterer._fit` does not run the `_fit` above.
        """
        linkage = getattr(self, "linkage_", None)
        children = getattr(self, "children_", None)

        if linkage is None and children is None:
            raise ContractViolationError(
                f"{type(self).__name__}._build_hierarchy set neither "
                f"`linkage_` nor `children_`, so there is no tree to cut. One "
                f"of the two formats must be produced; the other is derived."
            )

        if linkage is None:
            distances = getattr(self, "distances_", None)
            if distances is None:
                raise ContractViolationError(
                    f"{type(self).__name__} reported `children_` without "
                    f"`distances_`. A merge tree without its heights cannot be "
                    f"converted to a linkage matrix, and no threshold cut or "
                    f"dendrogram is possible without them."
                )
            self.linkage_ = self._linkage_from_children(children, distances)
            linkage = self.linkage_

        Z = np.asarray(linkage, dtype=float)
        if Z.ndim != 2 or Z.shape[1] != 4:
            raise ContractViolationError(
                f"{type(self).__name__} set `linkage_` with shape {Z.shape}; "
                f"SciPy's format is (m - 1, 4). `viz.plot_dendrogram` and "
                f"`cut` both read it directly."
            )
        self.linkage_ = Z

        if children is None:
            self.children_ = Z[:, :2].astype(int)
        if getattr(self, "distances_", None) is None:
            self.distances_ = Z[:, 2]

    @staticmethod
    def _linkage_from_children(children: Any, distances: Any) -> LinkageMatrix:
        """Convert scikit-learn's merge tree to a SciPy linkage matrix.

        The fourth column SciPy requires is the size of the cluster formed
        by each merge, which scikit-learn does not report. It is accumulated
        by walking the tree once: a node below `m` is an original
        observation and counts one, and anything above it is a merge whose
        size is already known because merges are recorded in order.
        """
        children = np.asarray(children, dtype=int)
        distances = np.asarray(distances, dtype=float).ravel()
        if children.ndim != 2 or children.shape[1] != 2:
            raise ContractViolationError(
                f"children_ must have shape (m - 1, 2); got {children.shape}."
            )
        if distances.shape[0] != children.shape[0]:
            raise ContractViolationError(
                f"children_ records {children.shape[0]} merges but distances_ "
                f"has {distances.shape[0]} heights; the two must correspond."
            )

        n_samples = children.shape[0] + 1
        sizes = np.zeros(children.shape[0], dtype=float)
        for step, (left, right) in enumerate(children):
            sizes[step] = sum(
                1.0 if child < n_samples else sizes[child - n_samples]
                for child in (left, right)
            )
        return np.column_stack([children.astype(float), distances, sizes])

    @staticmethod
    def _check_monotonic(Z: LinkageMatrix) -> None:
        """Refuse a height cut on a tree whose merge heights fall.

        Centroid and median linkage produce inversions, and a height
        threshold on an inverted tree does not correspond to any level of
        the dendrogram -- `fcluster` still returns something, which is why
        this is checked rather than left to fail visibly.

        Read from the fitted tree rather than from the criterion's
        `monotonic` declaration, so the check holds for an adapted method
        whose backend chose the criterion itself.
        """
        heights = np.asarray(Z, dtype=float)[:, 2]
        if heights.size and np.min(np.diff(heights)) < -_TOL:
            raise ValueError(
                "this hierarchy is not monotonic: merge heights decrease, so "
                "a height threshold does not correspond to a level of the "
                "dendrogram. Cut by n_clusters instead, or build the tree "
                "with a monotonic linkage criterion."
            )

    def _build_hierarchy(self, X: MatrixLike) -> None:
        """Construct the tree and set `linkage_`, `children_`, `distances_`.

        The one step that differs between agglomerative and divisive
        construction, and the only one a native method must write. Not
        abstract: an adapted method never reaches it, because its backend
        builds the tree.
        """
        raise NotImplementedError
