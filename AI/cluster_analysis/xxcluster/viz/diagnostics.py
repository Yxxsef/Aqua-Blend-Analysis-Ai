"""
Diagnostic figures.

The plots that justify a decision or expose its weakness: selection curves
behind a choice of |C|, silhouette plots showing which clusters are weak
rather than only the average, stability across repeats, and the
per-observation validity that reveals a good mean score hiding one
incoherent cluster.

These carry the argument of Sect. 4.3 and Sect. 4.5. A selection reported
without its curve, or a mean index reported without its distribution,
asks the reader to take the decision on trust.
"""

from __future__ import annotations

from typing import Any, Mapping


def plot_selection_curve(
    curve: Mapping[Any, float],
    *,
    selected: Any = None,
    criterion: str | None = None,
    ax: Any = None,
    **kwargs: Any,
) -> Any:
    """Plot an index against the swept parameter, marking the selection.

    Shows the curve whether or not the criterion found it conclusive; an
    inconclusive curve is the finding in that case, and hiding it would
    turn an arbitrary argmax into an apparent result.
    """
    raise NotImplementedError


def plot_silhouette(X: Any, labels: Any, *, metric: Any = "euclidean", ax: Any = None, **kwargs: Any) -> Any:
    """Draw per-observation silhouette values, grouped by cluster.

    More informative than the mean it summarises: it shows which clusters
    are weak and which observations sit on a boundary, both of which matter
    when a cluster is about to be given a name and acted on.
    """
    raise NotImplementedError


def plot_stability(analysis: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot the distribution of agreement across perturbed repeats."""
    raise NotImplementedError


def plot_cluster_profiles(profiles: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot per-cluster feature profiles in original units.

    The figure behind the naming step of Sect. 4.4; consumes the output of
    `evaluation.report.profile_clusters`.
    """
    raise NotImplementedError
