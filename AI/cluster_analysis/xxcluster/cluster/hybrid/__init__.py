"""
Hybrid methods.

Methods that combine techniques from any family, irrespective of where the
constituents sit -- the third group of Sect. 2.2.

Composition here is explicit: a hybrid holds its constituent components as
parameters, so each remains separately configurable, separately testable
and separately reportable. The SOM-then-k-means construction of Sect. 2.3
is the reference case: the map and the partitional method are unchanged,
and the hybrid contributes only the coupling between them.

Two rules keep the family from absorbing everything. A hybrid must state
which contract it presents -- if it produces `labels_`, it is a clusterer
regardless of what it contains -- and a composition that is merely a
preprocessing step followed by a clustering method is not a hybrid: that
is a pipeline, and belongs in `xxcluster.pipeline`.
"""

from __future__ import annotations
