"""
Partitional (iterative relocation) clustering methods.

Divides the dataset into near-homogeneous groups without building a
hierarchy, by optimising a criterion function of the kind given in
Def. 2. Following Sect. 2.2, crisp methods are subdivided by the strategy
used to optimise that criterion, while fuzzy methods are kept as one
group:

    sse_based/          criterion is a sum of squared error
    density_based/      clusters as dense regions, noise permitted
    model_based/        data as a realisation of a model
    graph_theoretic/    clustering as a cut on an affinity graph
    fuzzy/              soft assignment, one group as in the literature

Reserved for future use, to be created the same way -- a package with a
subfamily base class -- when the first method of the kind is added:
`subspace/`, `search_based/`, `miscellaneous/`. Their names are already
fixed in `core.types.SubFamily` so that a placeholder directory is not
needed to reserve them.
"""

from __future__ import annotations

# Subfamilies with registered methods, imported so that their `@register`
# lines run; see the note in `sse_based/__init__.py`.
from . import sse_based  # noqa: F401
