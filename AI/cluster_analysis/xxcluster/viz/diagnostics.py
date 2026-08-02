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

import numpy as np

from ..core.types import NOISE_LABEL
from ..core.validation import check_labels, ensure_fitted


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

    `criterion` names the rule in the legend rather than the title, since
    the same curve read by two rules gives two figures that must be
    distinguishable at a glance.
    """
    import matplotlib.pyplot as plt

    if not curve:
        raise ValueError("curve is empty; nothing was swept.")

    if ax is None:
        _, ax = plt.subplots()

    candidates = list(curve)
    scores = [curve[candidate] for candidate in candidates]
    ax.plot(candidates, scores, marker="o", label=criterion, **kwargs)

    if selected is not None:
        if selected not in curve:
            raise ValueError(
                f"selected={selected!r} is not among the swept candidates "
                f"{candidates}."
            )
        ax.axvline(selected, color="red", linestyle="--", linewidth=1)
        ax.plot([selected], [curve[selected]], marker="o", markersize=11,
                markerfacecolor="none", color="red")

    ax.set_xlabel("candidate")
    ax.set_ylabel("index")
    if criterion:
        ax.legend(loc="best", fontsize="small")
    return ax


def plot_silhouette(X: Any, labels: Any, *, metric: Any = "euclidean", ax: Any = None, **kwargs: Any) -> Any:
    """Draw per-observation silhouette values, grouped by cluster.

    More informative than the mean it summarises: it shows which clusters
    are weak and which observations sit on a boundary, both of which matter
    when a cluster is about to be given a name and acted on.

    Noise is excluded and reported in the axis label rather than drawn:
    the silhouette is undefined for observations in no cluster, and
    including them would depress the mean by an amount that depends on how
    many there are.
    """
    import matplotlib.pyplot as plt
    from sklearn.metrics import silhouette_samples

    labels = check_labels(labels)
    X = np.asarray(X) if not hasattr(X, "iloc") else X

    assigned = labels != NOISE_LABEL
    n_noise = int((~assigned).sum())
    values = silhouette_samples(
        X[assigned] if n_noise else X, labels[assigned], metric=metric
    )
    kept = labels[assigned]

    if ax is None:
        _, ax = plt.subplots()

    lower = 0
    for cluster in np.unique(kept):
        cluster_values = np.sort(values[kept == cluster])
        upper = lower + cluster_values.size
        ax.fill_betweenx(np.arange(lower, upper), 0, cluster_values, **kwargs)
        ax.text(-0.05, lower + cluster_values.size / 2, str(cluster),
                va="center", ha="right", fontsize="small")
        lower = upper + 10

    ax.axvline(values.mean(), color="0.4", linestyle="--", linewidth=1)
    suffix = f" ({n_noise} noise observations excluded)" if n_noise else ""
    ax.set_xlabel(f"silhouette value{suffix}")
    ax.set_yticks([])
    return ax


def plot_stability(analysis: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot the distribution of agreement across perturbed repeats.

    The distribution rather than the mean: a high mean with a wide spread
    means the method is sometimes reproducible, which is not stability and
    is the case Sect. 4.5 asks to be shown rather than summarised.
    """
    import matplotlib.pyplot as plt

    ensure_fitted(analysis, "agreements_")
    agreements = np.asarray(analysis.agreements_).ravel()

    if ax is None:
        _, ax = plt.subplots()

    ax.hist(agreements, bins=kwargs.pop("bins", 20), color="0.6", **kwargs)
    mean = float(np.mean(agreements))
    ax.axvline(mean, color="0.2", linestyle="--", linewidth=1,
               label=f"mean {mean:.3f}")
    ax.set_xlabel("pairwise agreement")
    ax.set_ylabel("pairs")
    ax.legend(loc="best", fontsize="small")
    return ax


def plot_cluster_profiles(profiles: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Plot per-cluster feature profiles in original units.

    The figure behind the naming step of Sect. 4.4; consumes the output of
    `evaluation.report.profile_clusters`.

    Plots `separation` -- the cluster's mean in standard deviations from
    the overall mean -- rather than the raw means, because features in
    different units cannot share an axis and the question a name has to
    answer is which features are unusual, not how large they are.
    """
    import matplotlib.pyplot as plt

    try:
        separation = profiles.xs("separation", axis=1, level=1)
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "profiles must come from evaluation.report.profile_clusters, which "
            "provides a `separation` column per feature."
        ) from exc

    if ax is None:
        _, ax = plt.subplots()

    features = list(separation.columns)
    clusters = list(separation.index)
    positions = np.arange(len(features))
    width = 0.8 / max(len(clusters), 1)

    for offset, cluster in enumerate(clusters):
        ax.bar(
            positions + offset * width,
            separation.loc[cluster].values,
            width=width,
            label=f"cluster {cluster}",
            **kwargs,
        )

    ax.axhline(0, color="0.3", linewidth=1)
    ax.set_xticks(positions + 0.4 - width / 2, features, rotation=45, ha="right")
    ax.set_ylabel("standard deviations from the overall mean")
    ax.legend(loc="best", fontsize="small")
    return ax
