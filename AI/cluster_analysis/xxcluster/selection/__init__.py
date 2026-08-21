"""
Model selection for unsupervised methods.

    n_clusters.py   choosing |C|, the procedure of Sect. 4.3
    stability.py    whether a partition survives resampling
    base.py         the shared selector contract

Selection without labels cannot be done by held-out error, so it rests on
two substitutes, one per module: a criterion curve over candidate values,
and reproducibility of the result under perturbation. They answer
different questions, and a partition that is optimal by the first and
unstable under the second is not a finding.

Applies to more than |C|: a density-based method has no |C| to choose but
still has density parameters to sweep, and the same machinery serves both.
Hence "selection" rather than "choosing k".
"""

from __future__ import annotations
