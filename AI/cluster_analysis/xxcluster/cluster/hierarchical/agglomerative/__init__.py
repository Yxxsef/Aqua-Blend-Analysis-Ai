"""
Agglomerative Hierarchical Clustering (AHC).

Bottom-up construction: begin with m singletons and repeatedly merge the
closest pair under the linkage criterion until one cluster remains.

Concrete methods go here, one module each. The variants differ only in
their linkage criterion, so `base.py` carries the merge loop and a method
is a declaration -- a linkage, a set of capabilities, a registered name --
rather than new code.
"""

from __future__ import annotations
