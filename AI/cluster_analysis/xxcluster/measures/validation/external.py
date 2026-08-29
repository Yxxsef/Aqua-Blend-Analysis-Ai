"""
External validity indices.

Compare a partition against a reference labelling -- the Rand index and
its adjusted form, mutual information, and the set-matching measures.

There is no ground truth for the operational data, so this group has two
uses here rather than the obvious one. On benchmark datasets with known
labels it validates that an implementation behaves as published, which is
the check a native implementation needs before its results are trusted.
And with one partition supplied as the "reference", the same indices
measure agreement between two clusterings -- which is how the stability
analysis in `xxcluster.selection.stability` scores resampled runs against
each other.

That second use is why this module's indices are also imported by the
relative group: the measure is identical, only the interpretation of the
second argument changes.
"""

from __future__ import annotations

from abc import ABC

from .base import BaseValidityIndex


class BaseExternalIndex(BaseValidityIndex, ABC):
    """An index comparing two labellings.

    Class attributes
    ----------------
    chance_corrected
        Whether the index is adjusted for agreement expected by chance.
        Material when the number of clusters differs between the two
        labellings: uncorrected indices rise with the number of clusters,
        so comparing partitions of different sizes needs a corrected one.
    symmetric
        Whether swapping the two labellings leaves the value unchanged.
        Required for the stability use above, where neither argument is
        privileged.
    """

    requires_labels_true = True
    requires_X = False

    chance_corrected: bool = False
    symmetric: bool = True
