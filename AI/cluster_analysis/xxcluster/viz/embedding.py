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
    """
    raise NotImplementedError


def plot_component_loadings(
    model: Any, *, feature_names: Sequence[str] | None = None, ax: Any = None, **kwargs: Any
) -> Any:
    """Plot the contribution of each feature to each component.

    Available for linear techniques only, and the reason to prefer one
    where it suffices: it says what a component means in terms of the
    measured variables, which no nonlinear embedding can.
    """
    raise NotImplementedError


def plot_feature_pairs(X: Any, labels: Any = None, *, features: Sequence[str] | None = None, **kwargs: Any) -> Any:
    """Pairwise scatter of selected original features, coloured by cluster.

    The check against an artefact of reduction: a partition visible in the
    measured variables is one the project can act on directly.
    """
    raise NotImplementedError
