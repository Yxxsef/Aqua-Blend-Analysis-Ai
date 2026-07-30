"""
Internal validity indices.

Score a partition using the data and the labels alone, with no reference
labelling -- the only group available for this project, since the
operational data carries no ground-truth regime labels. Silhouette,
Calinski-Harabasz and Davies-Bouldin are the ones the literature of
Sect. 2.3 uses for comparable work.

Every index in this group formalises the same intuition as Def. 2 --
compact clusters, well separated -- so a caveat applies to all of them and
belongs in the class docstring of each: they encode a notion of cluster
shape. An index built on distances to a centroid rewards the compact,
isotropic clusters the SSE family produces and penalises the elongated or
irregular ones a density-based method is designed to find. Used to choose
between methods of different families, such an index does not rank them
neutrally, which is a threat to validity for Sect. 4.5 rather than a
detail.
"""

from __future__ import annotations

from abc import ABC

from .base import BaseValidityIndex


class BaseInternalIndex(BaseValidityIndex, ABC):
    """An index computed from the data and the partition only.

    Class attributes
    ----------------
    assumes_shape
        The cluster geometry the index implicitly rewards, e.g. "compact,
        isotropic". Declared so the qualitative comparison can note when
        an index and a method disagree about what a cluster is.
    """

    requires_labels_true = False
    requires_X = True

    assumes_shape: str | None = None
