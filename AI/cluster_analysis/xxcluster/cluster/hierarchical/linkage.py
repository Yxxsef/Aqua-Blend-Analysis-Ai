"""
Linkage criteria.

A linkage criterion lifts a dissimilarity between observations to a
dissimilarity between clusters, and is the component AHC and DHC share.
It is kept separate from the methods for two reasons: the same criterion
is reused across methods, and the choice of criterion changes the shape of
cluster a method can recover -- single linkage chains, complete linkage
compacts, Ward minimises within-cluster variance -- which is a result to
report, not an implementation detail.

Criteria are registered by name so that `linkage="ward"` resolves the same
way whether the hierarchy is built natively or by an adapted backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...core.types import DissimilarityMatrix


class BaseLinkage(ABC):
    """Dissimilarity between two clusters, given the dissimilarities within.

    Class attributes
    ----------------
    name
        Registry key, e.g. "ward".
    requires_euclidean
        True where the criterion is only defined for Euclidean distance,
        as Ward's is. Checked against the method's `metric` at fit time,
        so an invalid combination fails before producing a result.
    monotonic
        True where merge heights are non-decreasing, so the dendrogram has
        no inversions and a height threshold is a valid cut.
    """

    name: str
    requires_euclidean: bool = False
    monotonic: bool = True

    @abstractmethod
    def between(
        self, D: DissimilarityMatrix, cluster_a: object, cluster_b: object
    ) -> float:
        """Return the dissimilarity between two clusters."""
        ...

    def update(self, D: DissimilarityMatrix, merged: object) -> DissimilarityMatrix:
        """Update the dissimilarity matrix after a merge.

        Criteria expressible by the Lance-Williams recurrence should
        override this: updating in place is what makes the merge loop
        affordable, versus recomputing `between` for every pair.
        """
        raise NotImplementedError
