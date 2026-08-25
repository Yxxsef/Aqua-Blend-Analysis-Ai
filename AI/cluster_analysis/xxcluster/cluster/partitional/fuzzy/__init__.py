"""
Fuzzy (soft) clustering methods.

Kept as a single group, as the literature of Sect. 2.2 does, rather than
subdivided by optimisation strategy like the crisp methods.

An observation belongs to every cluster to a degree, so the output is a
membership matrix and the partition of Def. 2 is recovered only by
defuzzifying it. Two consequences: the memberships carry information the
labels do not -- an observation sitting between two operating regimes is
visible as split membership and invisible as a label -- and validity
indices defined on crisp partitions apply to the defuzzified result only,
which must be stated when reporting them. Indices designed for fuzzy
partitions belong in `xxcluster.measures.validation`.
"""

from __future__ import annotations
