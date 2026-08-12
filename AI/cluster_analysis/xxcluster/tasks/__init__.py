"""
Analysis tasks: the horizontal extension point.

Everything else in this package is a component -- a method, a measure, a
step. A task is an end-to-end analysis: load a dataset, apply a protocol,
run components, produce results and figures. Tasks are where the package
grows sideways, into the work named in the introduction:

    Time-series clustering
        Clustering trajectories rather than independent observations.
        Needs a dissimilarity for series (DTW and relatives) in
        `measures.dissimilarity`, and a representation step in
        `pipeline.preprocess`; the clustering methods themselves are
        reused unchanged, which is the payoff of routing everything
        through d(., .).
    Anomaly detection
        Already has its contract in `core.base.BaseOutlierDetector`. Note
        the overlap with the density-based family, which identifies noise
        as part of clustering -- an anomaly detector makes that the
        objective rather than a by-product.
    Scenario generation
        Contract in `core.base.BaseGenerator`. The problem-driven
        formulation of Sect. 2.3: sample scenarios that reflect the
        regimes found in the operational data, and that respect the
        optimisation model consuming them. The interface to the MILP team,
        and so the task whose output format must be agreed with them
        before it is built.
    Demand forecasting
        Supervised, via `core.base.BasePredictor`, with cluster membership
        as a candidate feature.

Adding one means a subpackage here, plus whatever components it needs in
their own subpackages -- never a component defined inside a task, which
would put it beyond the reach of the registry and the comparison.

A task subpackage should hold the composition and the reporting, and no
algorithm.
"""

from __future__ import annotations
