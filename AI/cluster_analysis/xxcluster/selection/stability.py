"""
Stability analysis.

Asks whether a partition is a property of the data or of one particular
run. A method is refitted over perturbations -- resampled rows, added
noise, different seeds -- and the resulting partitions are compared with
each other using a symmetric external index from
`measures.validation.external`.

This is the closest available substitute for held-out validation, and it
addresses two of the weaknesses named in Sect. 2.1 directly: local optima,
where the same data and different seeds give different partitions, and
subjective hyperparameters, where a result that only holds at one setting
is not a robust one. A high internal index with low stability means the
method found a partition it can score well, not one the data supports. In other words,
this choice of method is inappropriate.

Stability is also a selection criterion in its own right -- preferring the
|C| whose partition is most reproducible -- so it composes with
`n_clusters.py` rather than duplicating it.

The general procedure is:
    1. Cluster the original dataset.
    2. Create a **slightly** modified dataset by:
            bootstrap sampling,
            subsampling,
            adding small amounts of noise,
            leaving out some observations.
    3. Cluster the modified dataset.
    4. Compare the new clustering to the original.
    5. Repeat many times.

> If the clusterings remain similar across repetitions,
> the clustering method is considered stable and appropriate.
> Note: the dataset should be slightly modified,
        otherwise it becomes an different dataset, and has no practical meaning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

from ..core.base import BaseComponent
from ..core.types import Labels, MatrixLike, Seed


class BasePerturbation(ABC):
    """Generates perturbed versions of a dataset.

    The perturbation defines what "stable" means, so it is explicit and
    named: stability under bootstrap resampling and stability under added
    measurement noise are different claims, and the second is the one that
    matters for sensor data.
    """

    name: str

    @abstractmethod
    def split(
        self, X: MatrixLike, *, n_repeats: int = 10, random_state: Seed = None
    ) -> Iterator[Any]:
        """Yield perturbed datasets, each with the index of retained rows.

        The index is needed to compare partitions on their common
        observations, which is the only place two resampled runs can be
        compared at all.
        """
        ...


class StabilityAnalysis(BaseComponent):
    """Measures how reproducible a method's partition is.

    Parameters
    ----------
    estimator
        Method under analysis; cloned per repeat.
    perturbation
        How the data is perturbed.
    n_repeats
        Number of perturbed fits. Enough that the reported spread means
        something, and recorded in the setup.
    scoring
        Symmetric external index used to compare two partitions.
    random_state
        Seed for the perturbations, without which the analysis is itself
        irreproducible.

    Fitted attributes
    -----------------
    stability_ : float
        Mean (Average) agreement across pairs of repeats.
    stability_std_ : float
        Spread, reported with the mean; even a high mean but with a high spread is
        not stability.
    agreements_ : ndarray
        The pairwise agreements themselves.
    consensus_labels_ : ndarray of shape (m,), optional
        Partition obtained by combining the repeats, where the analysis
        produces one. Often a better final answer than any single run.
    """

    stability_: float
    stability_std_: float
    agreements_: Any
    consensus_labels_: Labels

    def __init__(
        self,
        estimator: Any = None,
        *,
        perturbation: Any = None,
        n_repeats: int = 10,
        scoring: Any = None,
        random_state: Seed = None,
    ) -> None:
        self.estimator = estimator
        self.perturbation = perturbation
        self.n_repeats = n_repeats
        self.scoring = scoring
        self.random_state = random_state

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Refit over perturbations and score the resulting agreement."""
        raise NotImplementedError
