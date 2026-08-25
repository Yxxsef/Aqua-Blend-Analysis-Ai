"""
Figures.

    dendrogram.py    hierarchies
    embedding.py     reduced spaces, with or without labels
    diagnostics.py   selection curves and per-observation validity

Every function here takes fitted results and returns a figure without
fitting anything itself. A plotting routine that quietly refits produces a
figure of something other than the result being discussed.

The figures are for the document, so two conventions hold throughout: a
figure is reproducible from the artefact and seed recorded with it, and it
carries what is needed to read it -- which method, which measure, which
parameter values -- since a figure in a report is separated from the code
that made it.
"""

from __future__ import annotations
