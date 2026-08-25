"""
Dissimilarity and validation measures.

The two kinds of measurement Sect. 7.1 groups together, kept apart here
because they answer different questions:

    dissimilarity/      d(., .): how far apart two observations are, the
                        input a clustering method consumes
    validation/         how good a resulting partition is, the output the
                        comparison of Sect. 8 is built from

Both are components in their own right, registered and configurable, for
one reason: they are choices with consequences, not utilities. A method
paired with a different dissimilarity is a different method, and a
partition preferred by one validity index may be rejected by another.
Making them first-class means those choices are recorded with the result
instead of buried in a call site.
"""

from __future__ import annotations

# Groups with registered measures, imported so that their `@register`
# lines run; see the note in `cluster/partitional/sse_based/__init__.py`.
from . import validation  # noqa: F401
