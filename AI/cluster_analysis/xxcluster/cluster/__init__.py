"""
Clustering methods, organised by family.

The layout mirrors Sect. 7 of the documentation one directory per
subsection, so a method's code and its write-up sit at the same address in
both trees:

    hierarchical/   HCA: agglomerative and divisive construction
    partitional/    iterative relocation, by optimisation strategy
    hybrid/         combinations of methods from any family

Vertical extension -- adding a method -- means one new module under the
matching subfamily, a subclass of that subfamily's base, and one
`@register` line. Nothing outside that module changes: the selection,
evaluation and reporting layers find the method through the registry.

The classification is not universal; see Sect. 2.2 for why this one was
adopted. A method that resists placement belongs in `hybrid`, with the
reason recorded in its docstring, rather than in a new top-level family.
"""

from __future__ import annotations

# Families with registered methods, imported so that their `@register`
# lines run; see the note in `partitional/sse_based/__init__.py`.
from . import partitional  # noqa: F401
