"""
Plots of reduced spaces.

A two-dimensional scatter of an embedding, optionally coloured by cluster,
is the most persuasive and most misleading figure in this document. The
caution belongs in the code that draws it: well-separated groups in a
nonlinear embedding are not evidence of well-separated clusters in the
data, because the embedding was optimised to separate neighbourhoods. See
`dim_red.nonlinear`.

Hence the reporting rules these functions follow. The technique, its
parameters and its seed are recorded on the figure; where a
trustworthiness or stress value is available it is shown with it; and a
partition found in the original space, when drawn on an embedding, is
labelled as such rather than left to imply the embedding produced it.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from ..core.types import NOISE_LABEL
from ..core.validation import check_labels, ensure_fitted

#: Grey, and drawn first so assigned points sit on top of it. Noise is
#: context for the partition, not one of its clusters.
_NOISE_STYLE = {"color": "0.75", "marker": "x", "s": 18, "label": "noise"}


def _embedding_of(model: Any) -> np.ndarray:
    """Accept a fitted reducer or a bare array."""
    if hasattr(model, "embedding_"):
        ensure_fitted(model, "embedding_")
        return np.asarray(model.embedding_)
    return np.asarray(model)


def plot_embedding(
    embedding: Any,
    labels: Any = None,
    *,
    ax: Any = None,
    components: tuple[int, int] = (0, 1),
    annotate: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Scatter a two-dimensional slice of an embedding.

    Parameters
    ----------
    labels
        Cluster assignment used for colour. Noise (-1) is drawn distinctly
        rather than as another cluster.
    annotate
        Provenance shown on the figure: technique, parameters, seed, and
        the trustworthiness or stress where known.

    The axes are labelled by component index rather than left bare,
    because the pair plotted is a choice: components (0, 2) of a linear
    reduction is a different figure from (0, 1) and the reader cannot tell
    them apart otherwise.
    """
    import matplotlib.pyplot as plt

    points = _embedding_of(embedding)
    if points.ndim != 2:
        raise ValueError(f"embedding must be 2-D; got shape {points.shape}.")

    i, j = components
    if max(i, j) >= points.shape[1]:
        raise ValueError(
            f"components {components} requested, but the embedding has only "
            f"{points.shape[1]}."
        )

    if ax is None:
        _, ax = plt.subplots()

    if labels is None:
        ax.scatter(points[:, i], points[:, j], **kwargs)
    else:
        labels = check_labels(labels, n_samples=points.shape[0])
        noise = labels == NOISE_LABEL
        if noise.any():
            ax.scatter(points[noise, i], points[noise, j], **_NOISE_STYLE)
        assigned = ~noise
        ax.scatter(
            points[assigned, i],
            points[assigned, j],
            c=labels[assigned],
            cmap=kwargs.pop("cmap", "tab10"),
            **kwargs,
        )
        if noise.any():
            ax.legend(loc="best", fontsize="small")

    ax.set_xlabel(f"component {i}")
    ax.set_ylabel(f"component {j}")

    if annotate:
        ax.set_title(
            ", ".join(f"{key}={value}" for key, value in annotate.items()),
            fontsize="small",
        )
    return ax


def plot_component_loadings(
    model: Any, *, feature_names: Sequence[str] | None = None, ax: Any = None, **kwargs: Any
) -> Any:
    """Plot the contribution of each feature to each component.

    Available for linear techniques only, and the reason to prefer one
    where it suffices: it says what a component means in terms of the
    measured variables, which no nonlinear embedding can.

    Refuses a technique with no `components_`, rather than falling back to
    something approximate: a loadings figure for a nonlinear embedding
    would assert a feature-level reading the technique does not support.
    """
    import matplotlib.pyplot as plt

    components = getattr(model, "components_", None)
    if components is None:
        components = getattr(getattr(model, "backend_", None), "components_", None)
    if components is None:
        raise NotImplementedError(
            f"{type(model).__name__} has no `components_`, so its embedding "
            f"cannot be read as a combination of the measured features. "
            f"Loadings exist for linear techniques only."
        )

    components = np.asarray(components)
    if feature_names is None:
        feature_names = getattr(model, "feature_names_in_", None)
    if feature_names is None:
        feature_names = [f"x{k}" for k in range(components.shape[1])]

    if ax is None:
        _, ax = plt.subplots()

    loadings = pd.DataFrame(
        components.T,
        index=list(feature_names),
        columns=[f"component {k}" for k in range(components.shape[0])],
    )
    image = ax.imshow(loadings.values, cmap=kwargs.pop("cmap", "RdBu_r"), **kwargs)
    ax.set_xticks(range(loadings.shape[1]), loadings.columns, rotation=45, ha="right")
    ax.set_yticks(range(loadings.shape[0]), loadings.index)
    ax.figure.colorbar(image, ax=ax, label="loading")
    return ax


def plot_feature_pairs(
    X: Any,
    labels: Any = None,
    *,
    features: Sequence[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Pairwise scatter of selected original features, coloured by cluster.

    The check against an artefact of reduction: a partition visible in the
    measured variables is one the project can act on directly.

    Returns the grid of axes. `features` is worth passing: the number of
    panels grows with the square of the number of features, and a grid
    nobody can read is not a check on anything.
    """
    import matplotlib.pyplot as plt

    frame = X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X))
    if features is not None:
        frame = frame[list(features)]
    frame = frame.select_dtypes(include="number")

    names = list(frame.columns)
    n = len(names)
    if n < 2:
        raise ValueError("at least two numeric features are needed for a pair plot.")

    fig, axes = plt.subplots(n, n, figsize=kwargs.pop("figsize", (2.2 * n, 2.2 * n)))
    colours = None if labels is None else check_labels(labels, n_samples=len(frame))

    for row, y_name in enumerate(names):
        for column, x_name in enumerate(names):
            ax = axes[row, column]
            if row == column:
                ax.hist(frame[x_name].dropna(), bins=20, color="0.6")
            else:
                ax.scatter(
                    frame[x_name],
                    frame[y_name],
                    c=colours,
                    cmap=kwargs.get("cmap", "tab10"),
                    s=kwargs.get("s", 8),
                )
            if row == n - 1:
                ax.set_xlabel(x_name, fontsize="small")
            if column == 0:
                ax.set_ylabel(y_name, fontsize="small")
            ax.tick_params(labelsize="x-small")

    fig.tight_layout()
    return axes
