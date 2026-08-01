"""
Dendrograms.

The characteristic figure of HCA, and the one that carries information no
table does: where the merge heights jump, which is the visual counterpart
of choosing a cut level, and whether the tree is balanced or chains.

Reads `linkage_` from any fitted `HierarchyMixin`, so the same function
serves agglomerative and divisive methods and any adapted backend.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from ..core.validation import ensure_fitted


def _linkage_of(model: Any) -> np.ndarray:
    """Return a fitted model's linkage matrix, or the matrix itself.

    Accepting either means a stored linkage can be replotted without
    reconstructing the model that produced it.
    """
    if hasattr(model, "linkage_"):
        ensure_fitted(model, "linkage_")
        return np.asarray(model.linkage_)

    linkage = np.asarray(model)
    if linkage.ndim != 2 or linkage.shape[1] != 4:
        raise ValueError(
            f"expected a fitted hierarchical method with `linkage_`, or a "
            f"SciPy linkage matrix of shape (m - 1, 4); got shape "
            f"{linkage.shape}."
        )
    return linkage


def plot_dendrogram(
    model: Any,
    *,
    ax: Any = None,
    truncate_mode: str | None = None,
    color_threshold: float | None = None,
    labels: Sequence[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Draw the dendrogram of a fitted hierarchical method.

    Parameters
    ----------
    truncate_mode
        How to abbreviate the tree; a full dendrogram over the whole
        dataset is unreadable at these sizes.
    color_threshold
        Cut height to colour by. Set it to the height the reported
        partition was cut at, so the figure shows the actual result rather
        than a default.
    """
    import matplotlib.pyplot as plt
    from scipy.cluster.hierarchy import dendrogram

    linkage = _linkage_of(model)
    if ax is None:
        _, ax = plt.subplots()

    dendrogram(
        linkage,
        ax=ax,
        truncate_mode=truncate_mode,
        color_threshold=color_threshold,
        labels=list(labels) if labels is not None else None,
        **kwargs,
    )

    if color_threshold is not None:
        # Drawn, because a coloured dendrogram without its cut line invites
        # the reader to infer the cut from the colours alone.
        ax.axhline(color_threshold, color="0.4", linestyle="--", linewidth=1)

    ax.set_ylabel("merge height")
    return ax


def plot_merge_heights(model: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot merge height against merge step.

    The quantitative reading of the same information: a jump in height is
    the elbow used to choose a cut, and it is easier to defend from this
    curve than from the tree by eye.

    Plotted in reverse, so the horizontal axis reads as the number of
    clusters remaining rather than as merges performed -- the quantity the
    selection of Sect. 4.3 is actually about.
    """
    import matplotlib.pyplot as plt

    heights = _linkage_of(model)[:, 2]
    if ax is None:
        _, ax = plt.subplots()

    remaining = np.arange(len(heights), 0, -1)
    ax.plot(remaining, heights, marker="o", **kwargs)
    ax.invert_xaxis()
    ax.set_xlabel("clusters remaining")
    ax.set_ylabel("merge height")
    return ax
