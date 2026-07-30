# xxcluster

Codebase for `documentation/main.pdf`, *On the Search for Cluster Analysis*.

**Status: skeleton.** The structure, the contracts and the conventions are
settled. No method is implemented. Abstract methods have empty bodies;
concrete methods not yet written raise `NotImplementedError`.

## Layout

| Directory | Holds | Document |
|---|---|---|
| `core/` | The contract: base classes, mixins, protocols, tags, registry | — |
| `cluster/` | Clustering methods, by family | Sect. 7 |
| `dim_red/` | Dimensionality reduction, and intrinsic dimension | Sect. 6 |
| `measures/` | Dissimilarity measures and validity indices | Sect. 7.1 |
| `pipeline/` | Preprocessing steps and composition | Sect. 3.3 |
| `selection/` | Choosing \|C\|, stability analysis | Sect. 4.3 |
| `evaluation/` | The shared protocol, the comparison tables | Sect. 4, 8 |
| `io/` | Dataset loading, artefact storage | Sect. 3.1, App. A |
| `viz/` | Figures | — |
| `tasks/` | End-to-end analyses | — |

`core/` depends on nothing else in the package. Everything else depends on
`core/`. An import from `core/` into a sibling subpackage is a design
error.

## The contract

Every component is a scikit-learn estimator, inheriting
`sklearn.base.BaseEstimator` through `core.base.BaseComponent`. That is
what buys `Pipeline`, the `*SearchCV` classes, `clone`, `check_estimator`
and interchangeability with third-party estimators.

Four rules, enforced by `check_estimator` and by the contract checks:

1. **Parameters** are accepted in `__init__` only, stored unmodified under
   their own name, and never validated there.
2. **Fitted state** is set by `fit`, named with a trailing underscore, and
   absent until fitting succeeds.
3. **`fit` is a template method.** Override the private `_fit`; do not
   override `fit`.
4. **Capabilities are declared**, once per concrete class, as
   `_capabilities`. A declaration contradicting the interface is a
   `ContractViolationError`.

Capabilities are not documentation. The registry shortlists methods from
them, and the qualitative comparison table of Sect. 8.2 is generated from
them.

## Adding a clustering method (vertical)

1. Find its subfamily under `cluster/`. If the subfamily package does not
   exist yet, create it with an `__init__.py` and a `base.py`, using an
   existing one as the model. Its name should already be in
   `core.types.SubFamily`.
2. Write one module for the method. Subclass the subfamily base, and mix in
   the capabilities it actually has from `core.mixins` — `InductiveMixin`
   only if it can label unseen observations, `NoiseAwareMixin` only if it
   can decline to assign one.
3. Prefer adapting a mature implementation: subclass `AdaptedClusterer` and
   declare `_backend_import`, `_param_map` and `_attr_map`. Implement
   `_fit` natively where no good implementation exists, or where following
   the formulation in the document is the point. Record which route was
   taken in `_capabilities.backend`.
4. Declare `_capabilities`, filling the assumptions and complexity fields
   from the method's documentation section, and set `doc_label` to that
   section's label.
5. Register it: `@register("method_name")`. Names are permanent — they
   appear in stored artefacts and in the document's tables.
6. Copy `documentation/sections/clustering_methods/00-template.tex` into
   the matching family directory and add its `\input` line.

Nothing outside the new module changes. Selection, evaluation and reporting
find the method through the registry.

## Adding a task (horizontal)

Tasks — time-series clustering, anomaly detection, scenario generation,
demand forecasting — get a subpackage under `tasks/`, subclassing
`tasks.base.BaseTask`.

A task composes components; it does not implement algorithms. Anything
reusable goes in the subpackage for its kind, where the registry and the
comparison can reach it: a dissimilarity for series in
`measures/dissimilarity/`, a detector under `core.base.BaseOutlierDetector`,
a generator under `core.base.BaseGenerator`. A component defined inside a
task is invisible to both.

## Conventions

- Notation follows the document's table: `n` observations, `d` features,
  `|C|` clusters, `d(., .)` for dissimilarity.
- Noise is label `-1`, everywhere.
- `n_clusters` is a request; `n_clusters_` is a result.
- Docstrings cite the document by section, and literature by its
  `literature.bib` key.
- `from __future__ import annotations` at the top of every module.

## Dependencies

`numpy`, `scikit-learn`. Backends for adapted methods (`scipy`,
`hdbscan`, `umap-learn`, and others) are optional and imported at fit
time, not at import time, so a missing one raises
`BackendUnavailableError` from the method that needs it and leaves the rest
of the package usable.
