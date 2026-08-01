"""
Relative validity criteria.

Compare partitions with each other rather than scoring one in isolation:
the same method at several values of |C|, or several methods on the same
data. This is the group the choice of |C| in Sect. 4.3 rests on, i.e. the
elbow of a criterion curve, the knee of a gap statistic, the peak of an
index across candidate values.

The distinction from the internal group is the unit of assessment. An
internal index scores one partition; a relative criterion reads a
sequence of scores and selects from it. The two are related, as most
relative criteria are built on an internal index evaluated repeatedly,
but the selection rule is separate from the index, and worth naming: the
same silhouette curve yields different answers under "take the maximum"
and "take the largest |C| within one standard error of the maximum".

The criteria live here; the procedure that generates the candidates and
applies one is `xxcluster.selection.n_clusters`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence


class BaseRelativeCriterion(ABC):
    """Selects among candidate partitions from their scores.

    Class attributes
    ----------------
    name
        Registry key, e.g. "elbow", "gap_statistic".
    base_index
        Name of the index whose curve the criterion reads, where it uses
        one. Recorded because "the elbow" is not a result on its own: the
        curve it was read from is part of the finding.
    """

    name: str
    base_index: str | None = None

    @abstractmethod
    def select(self, scores: Mapping[Any, float], **kwargs: Any) -> Any:
        """Return the candidate key the criterion prefers.

        `scores` maps a candidate, usually a value of |C| to its
        score. Returning the key rather than the score keeps the criterion
        independent of what is being varied, so the same rule applies to a
        sweep over a density parameter.
        """
        ...

    def curve(self, scores: Mapping[Any, float]) -> Sequence[float]:
        """Return the curve the criterion reads, for plotting.

        Selection is a judgement, and a reader is entitled to see the curve
        behind it, especially where the criterion found no clear
        structure. Consumed by `xxcluster.viz.diagnostics`.
        """
        raise NotImplementedError

    def is_conclusive(self, scores: Mapping[Any, float]) -> bool:
        """Report whether the curve supports a selection at all.

        A flat or monotone curve means the data does not distinguish the
        candidates. Saying so is a valid outcome, and better than returning
        an arbitrary argmax that later reads as a finding.
        """
        raise NotImplementedError
