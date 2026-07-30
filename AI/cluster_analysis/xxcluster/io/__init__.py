"""
Data access and artefact storage.

    datasets.py    loading the feature matrix the analysis operates on
    artifacts.py   storing what a run produced

The boundary this subpackage defends: nothing else in the package reads a
file or knows a path. A clustering method receives an array, and is
therefore testable on synthetic data and reusable on any dataset; a
loader knows about the AquaBlend schema, and is the only thing that does.

The upstream data itself is owned by the Data Engineering team, per the
repository's folder ownership. This subpackage consumes what that team
publishes and does not clean, correct or reshape it beyond the documented
preprocessing -- a data problem found here is raised with them, not
patched here, where the patch would be invisible to everyone else using
the same data.
"""

from __future__ import annotations
