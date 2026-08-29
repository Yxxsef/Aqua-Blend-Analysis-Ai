"""
Cluster validation measures.

Implement the different validation measures for clustering results, in three groups:

    internal.py     uses the data and the partition only
    external.py     compares the partition against a reference labelling
    relative.py     compares partitions with each other, to choose among them

These are the definitions; the harness that runs them across methods and
assembles the tables of Sect. 4.2 and Sect. 8.1 is
`xxcluster.evaluation`. Keeping the two apart means an index is defined
once and reported everywhere.

Two rules apply to every index here, and both are enforced through the
base class rather than left to the caller. Its direction must be declared,
since higher is better for some and worse for others and a comparison that
gets this wrong is silently inverted. And its treatment of noise must be
declared, since an index defined on a partition of the whole dataset is
not defined on one where observations are labelled -1, hence excluding them
flatters a density-based method by scoring only the points it was
confident about.
"""

from __future__ import annotations

# Imported for its registration side effect; see the note in
# `cluster/partitional/sse_based/__init__.py`.
from . import internal  # noqa: F401
