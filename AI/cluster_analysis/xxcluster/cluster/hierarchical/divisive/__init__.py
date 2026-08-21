"""
Divisive Hierarchical Clustering (DHC).

Top-down construction: begin with one cluster containing every
observation and repeatedly split the cluster selected by the splitting
rule.

Concrete methods go here, one module each. The splitting step is often a
partitional method applied to a subset, which makes this the natural home
for the bisecting variants; a method whose splitting step is doing most of
the work may belong in `hybrid/` instead.
"""

from __future__ import annotations
