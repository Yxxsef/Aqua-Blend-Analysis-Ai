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
    raise NotImplementedError


def plot_merge_heights(model: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot merge height against merge step.

    The quantitative reading of the same information: a jump in height is
    the elbow used to choose a cut, and it is easier to defend from this
    curve than from the tree by eye.
    """
    raise NotImplementedError
