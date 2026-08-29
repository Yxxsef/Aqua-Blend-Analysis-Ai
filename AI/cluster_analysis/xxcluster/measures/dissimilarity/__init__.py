"""
Dissimilarity and similarity measures.

Implement the dissimilarity and similarity measures used in the different clustering
methods.

Def. 1 and Def. 2 of the documentation draw the distinction this
subpackage is built on: a mathematical metric satisfies identity,
symmetry and the triangle inequality, whereas a dissimilarity used by a
clustering method need not. Both are admissible; which one is in use is
declared, because a method whose correctness depends on the triangle
inequality -- Ward's criterion, or any acceleration that prunes distance
computations -- cannot be given a measure that violates it.

Measures reach the methods by two routes: by name, where the backend
resolves it, or as a precomputed matrix via `PrecomputedMixin`. The second
route is what allows a measure defined here to be used with any method
that supports it, including adapted ones that know nothing about this
package -- and so is the extension point for mixed-type data and, later,
for time-series dissimilarities such as DTW.
"""

from __future__ import annotations
