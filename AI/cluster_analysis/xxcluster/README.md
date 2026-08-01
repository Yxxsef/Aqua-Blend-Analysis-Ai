# xxcluster

Cluster analysis for the AquaBlend dataset — the codebase behind `documentation/main.pdf`, *On the Search for Cluster Analysis*.

The document and the package share one structure: a method's write-up and its implementation sit at matching addresses in the two trees, and docstrings cite the document by section number.

**Status: skeleton.** Structure, contracts and conventions are settled. No
method is implemented yet — abstract methods have empty bodies, and concrete
methods not yet written raise `NotImplementedError`.

Two exceptions, both in `core/` and both tested (`python -m pytest` from
`cluster_analysis/`):

- **`BaseComponent.fit`** and the steps it runs — the template method every
  component inherits. A subclass now only overrides `_fit`.
- **The precomputed-matrix checks** in `core/validation.py`. They came first
  because the failures they catch — a similarity matrix passed as a
  dissimilarity, a squared distance, a non-zero diagonal — produce a
  plausible-looking partition rather than an error.

A component whose only content is a `_fit` override already passes
scikit-learn's `check_estimator`.

## Layout

| Directory | Holds | Document |
|---|---|---|
| `core/` | The contract: base classes, mixins, protocols, tags, registry | — |
| `cluster/` | Clustering methods, by family | Sect. 7 |
| `dim_red/` | Dimensionality reduction, intrinsic dimension | Sect. 6 |
| `measures/` | Dissimilarity measures and validity indices | Sect. 7.1 |
| `pipeline/` | Preprocessing steps and composition | Sect. 3.3 |
| `selection/` | Choosing \|C\|, stability analysis | Sect. 4.3 |
| `evaluation/` | The shared protocol, the comparison tables | Sect. 4, 8 |
| `io/` | Dataset loading, artefact storage | Sect. 3.1, App. A |
| `viz/` | Figures | — |
| `tasks/` | End-to-end analyses; the horizontal extension point | — |

`core/` depends on nothing else in the package; everything else depends on `core/`.

## The contract

Every component is a scikit-learn estimator, inheriting `BaseEstimator` through `core.base.BaseComponent`.

1. **Parameters** go in `__init__` only, stored unmodified, never validated there.
2. **Fitted state** is set by `fit` and named with a trailing underscore.
3. **`fit` is a template method** — override the private `_fit`.
4. **Capabilities are declared** as `_capabilities`, and are read by the
   registry and by the comparison table of Sect. 8.2.

## Install

```bash
pip install -r ../requirements.txt
```

Needs `numpy`, `scipy`, `scikit-learn`, `pandas`; `matplotlib` for `viz/`.
Backends for adapted methods are optional and imported at fit time.

## Further reading

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — what each folder and file does, how a
  run flows through them, and where to extend.
- **[../CONTRIBUTING.md](../CONTRIBUTING.md)** — how to add a method to the code
  and its section to the document, and how to evidence it in a notebook.
