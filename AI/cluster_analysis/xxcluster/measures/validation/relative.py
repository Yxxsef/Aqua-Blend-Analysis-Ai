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

import math
from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from ...core.registry import register
from ...core.types import ComponentKind
from .base import BaseValidityIndex


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

    def curve(self, scores: Mapping[Any, float]) -> Mapping[Any, float]:
        """Return the curve the criterion reads, for plotting.

        Selection is a judgement, and a reader is entitled to see the curve
        behind it, especially where the criterion found no clear
        structure. Consumed by `xxcluster.viz.diagnostics`.

        Keyed by candidate rather than a bare sequence, because
        `viz.plot_selection_curve` indexes the curve by candidate and
        checks that the selection is among them.
        """
        raise NotImplementedError

    def is_conclusive(self, scores: Mapping[Any, float]) -> bool:
        """Report whether the curve supports a selection at all.

        A flat or monotone curve means the data does not distinguish the
        candidates. Saying so is a valid outcome, and better than returning
        an arbitrary argmax that later reads as a finding.
        """
        raise NotImplementedError


def _finite(scores: Mapping[Any, float]) -> dict[Any, float]:
    """Return the entries whose score is a finite number, in sweep order.

    A failed run enters the sweep as NaN rather than as a gap, so that it
    is still reported in the table. `is_better` already refuses to let a
    NaN win a selection; the shape tests in `is_conclusive` need it dropped
    instead, since a NaN would make every comparison false and report a
    real curve as flat.
    """
    return {k: float(v) for k, v in scores.items() if math.isfinite(float(v))}


@register("max", kind=ComponentKind.VALIDITY_INDEX)
class MaxCriterion(BaseRelativeCriterion):
    """Take the best-scoring candidate, in the direction its index declares.

    The simplest rule, and the one every other is measured against. "Best"
    is not "largest": Davies-Bouldin is minimised, so the direction comes
    from the index through `is_better` and never from a comparison written
    here.

    Parameters
    ----------
    index
        The validity index whose curve is being read. Required, with no
        default, for the same reason `higher_is_better` has none: a
        criterion that assumes a direction is one that will eventually
        select the worst candidate and report it as the best.
    flat_tolerance
        A curve whose spread is below this fraction of the index's scale
        does not distinguish its candidates, and `is_conclusive` reports
        False. Declared as a parameter rather than written into the
        comparison, so the write-up can state the threshold a selection
        had to clear.
    min_margin
        The winner must beat the runner-up by at least this fraction of
        the index's scale. Separates a peak from a tie.

    Notes
    -----
    Ties are broken by sweep order: the first candidate to attain the best
    score wins, because `is_better` is strict. Where |C| is swept upward
    that is the smallest |C| achieving the score, which is the
    conservative choice.
    """

    name = "max"

    def __init__(
        self,
        index: BaseValidityIndex,
        *,
        flat_tolerance: float = 0.01,
        min_margin: float = 0.01,
    ) -> None:
        self.index = index
        self.base_index = getattr(index, "name", None)
        self.flat_tolerance = flat_tolerance
        self.min_margin = min_margin

    def _scale(self, values: Sequence[float]) -> float:
        """Return the scale the thresholds are fractions of.

        The index's declared range where it has one, since that is what
        makes a margin comparable across datasets. Falling back to the
        observed magnitude keeps an unbounded index usable, at the cost of
        a threshold that means something slightly different.
        """
        declared = getattr(self.index, "range_", None)
        if declared is not None:
            low, high = declared
            if math.isfinite(low) and math.isfinite(high) and high > low:
                return float(high - low)
        magnitude = max((abs(v) for v in values), default=0.0)
        return magnitude if magnitude > 0 else 1.0

    def select(self, scores: Mapping[Any, float], **kwargs: Any) -> Any:
        """Return the candidate the index scores best."""
        if not scores:
            raise ValueError(
                "scores is empty; nothing was swept, so there is nothing to "
                "select from."
            )

        best_key, best_score = None, None
        for candidate, score in scores.items():
            if best_score is None or self.index.is_better(score, best_score):
                best_key, best_score = candidate, score

        if best_key is None or not math.isfinite(float(best_score)):
            raise ValueError(
                f"no candidate scored a finite value under "
                f"{self.base_index!r}; every run in the sweep failed."
            )
        return best_key

    def curve(self, scores: Mapping[Any, float]) -> Mapping[Any, float]:
        """Return the swept scores, in sweep order.

        A copy, so a caller plotting the curve cannot mutate the record the
        selection was made from. The order is preserved rather than sorted
        by score: re-sorting misaligns the figure from the sweep it
        describes.
        """
        return dict(scores)

    def is_conclusive(self, scores: Mapping[Any, float]) -> bool:
        """Report whether the curve supports taking its maximum.

        Three ways it does not, and each is a real outcome rather than a
        failure. Too few candidates to see a shape. A curve flat enough
        that its candidates are indistinguishable. And a monotone curve,
        where the best candidate sits at an end of the sweep, so the
        selection is an artefact of where the sweep stopped and the sweep
        should be widened instead.
        """
        finite = _finite(scores)
        if len(finite) < 3:
            return False

        values = list(finite.values())
        scale = self._scale(values)

        spread = max(values) - min(values)
        if spread / scale < self.flat_tolerance:
            return False

        best = self.select(finite)
        runner_up = None
        for candidate, score in finite.items():
            if candidate == best:
                continue
            if runner_up is None or self.index.is_better(score, runner_up):
                runner_up = score
        if runner_up is not None:
            if abs(finite[best] - runner_up) / scale < self.min_margin:
                return False

        keys = list(finite)
        if best in (keys[0], keys[-1]) and self._is_monotone(values):
            return False

        return True

    @staticmethod
    def _is_monotone(values: Sequence[float]) -> bool:
        """Report whether the curve only ever rises, or only ever falls."""
        rising = all(b >= a for a, b in zip(values, values[1:]))
        falling = all(b <= a for a, b in zip(values, values[1:]))
        return rising or falling


@register("elbow", kind=ComponentKind.VALIDITY_INDEX)
class ElbowCriterion(BaseRelativeCriterion):
    """Take the candidate furthest from the chord of the curve.

    Written for the monotone case the maximum cannot read: an SSE curve
    falls with every added cluster, so its best value is always the largest
    |C| swept, and the informative point is where the improvement stops
    paying. The chord from the first swept candidate to the last is the
    curve the data would trace with no such point; the elbow is where it
    departs from it furthest.

    Both axes are normalised to the unit square before the distance is
    measured, so the answer does not depend on the units of the index or on
    how wide the sweep was.

    Parameters
    ----------
    index
        The index whose curve is read. Recorded for `base_index`; the
        geometry itself is direction-free, which is why an elbow can be
        read from a minimised criterion without inverting it.
    min_curvature
        How far, as a fraction of the chord's length, the curve must depart
        from the chord before the departure counts. A straight line has no
        elbow, and reporting one from a straight line is how a rounded
        number becomes a finding.
    """

    name = "elbow"

    def __init__(
        self,
        index: BaseValidityIndex | None = None,
        *,
        min_curvature: float = 0.05,
    ) -> None:
        self.index = index
        self.base_index = getattr(index, "name", None)
        self.min_curvature = min_curvature

    def _distances(self, scores: Mapping[Any, float]) -> dict[Any, float]:
        """Return each candidate's normalised distance from the chord.

        Sorted on the candidate as a number, but keyed by the candidate as
        it was given. A selection is handed straight to
        `viz.plot_selection_curve`, which tests membership in the curve, so
        returning 3.0 where the caller swept 3 would depend on int and
        float hashing alike to keep working.
        """
        finite = _finite(scores)
        try:
            points = sorted((float(k), k, v) for k, v in finite.items())
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "the elbow criterion needs numeric candidates, since it "
                "measures a distance along the swept axis. Got "
                f"{list(finite)!r}."
            ) from exc

        if len(points) < 3:
            return {}

        keys = [p[1] for p in points]
        xs = [p[0] for p in points]
        ys = [p[2] for p in points]
        x_span = xs[-1] - xs[0]
        y_span = max(ys) - min(ys)
        if x_span == 0 or y_span == 0:
            return {}

        unit = [
            ((x - xs[0]) / x_span, (y - min(ys)) / y_span)
            for x, y in zip(xs, ys)
        ]
        (x0, y0), (x1, y1) = unit[0], unit[-1]
        chord = math.hypot(x1 - x0, y1 - y0)
        if chord == 0:
            return {}

        return {
            keys[i]: abs(
                (x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)
            ) / chord
            for i, (x, y) in enumerate(unit)
        }

    def select(self, scores: Mapping[Any, float], **kwargs: Any) -> Any:
        """Return the candidate at the greatest departure from the chord."""
        if not scores:
            raise ValueError(
                "scores is empty; nothing was swept, so there is nothing to "
                "select from."
            )
        distances = self._distances(scores)
        if not distances:
            raise ValueError(
                "an elbow needs at least three candidates with distinct "
                "finite scores; this curve has no shape to read."
            )
        return max(distances, key=distances.get)

    def curve(self, scores: Mapping[Any, float]) -> Mapping[Any, float]:
        """Return the swept scores, in sweep order."""
        return dict(scores)

    def is_conclusive(self, scores: Mapping[Any, float]) -> bool:
        """Report whether the curve bends enough to have an elbow at all."""
        distances = self._distances(scores)
        if not distances:
            return False
        return max(distances.values()) >= self.min_curvature