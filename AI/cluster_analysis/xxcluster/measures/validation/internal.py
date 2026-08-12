"""
Internal validity indices.

Score a partition using the data and the labels alone, with no reference
labelling, e.g. Silhouette, Calinski-Harabasz and Davies-Bouldin.

Every index in this group formalises the same intuition as Def. 2, i.e.
compact clusters, well separated, so a caveat applies to all of them and
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

from ...core.registry import register
from ...core.validation import check_labels
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

    assumes_shape: str | None = None    # for sake of clarity about the index



@register("silhouette")
class Silhouette(BaseInternalIndex):
    """
        Writing something here
    """
    name = "silhouette"
    higher_is_better = True
    range_ = (-1.0, 1.0)
    handles_noise = False
    assumes_shape = "compact, isotropic"

    def score(self, X = None, labels = None, *, labels_true = None, metric = "euclidean", **kwargs):
        from sklearn.metrics import silhouette_score
        labels = check_labels(labels, allow_noise = self.handles_noise)
        return silhouette_score(X, labels, metric = metric)

@register("calinski_harabasz")
class CalinskiHarabasz(BaseInternalIndex):
    """Calinski-Harabasz internal validity index."""
    
    name = "calinski_harabasz"
    higher_is_better = True
    range_ = (0.0, float("inf"))
    handles_noise = False
    assumes_shape = "compact, isotropic"
    
    def score(
        self,
        X=None,
        labels=None,
        *,
        labels_true=None,
        metric="euclidean",
        **kwargs,
    ):
        from sklearn.metrics import calinski_harabasz_score
    
        labels = check_labels(labels, allow_noise=self.handles_noise)
    
        if len(set(labels)) < 2:
            raise ValueError("Calinski-Harabasz requires at least two clusters.")
    
        return float(calinski_harabasz_score(X, labels))