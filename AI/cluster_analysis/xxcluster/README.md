# xxcluster

Cluster analysis for the AquaBlend dataset — the codebase behind `documentation/main.pdf`, *In Search of Cluster Analysis*.

The document and the package share one structure: a method's write-up and its implementation sit at matching addresses in the two trees, and docstrings cite the document by section number.

**Status: scaffolding complete, no method implemented.** No clustering method or dimensionality reduction technique exists yet; their `_fit` bodies are the work of the sprints ahead.

| Area | What works |
|---|---|
| `core/base.py` | `fit` and the steps it runs — subclasses override only `_fit` |
| `core/validation.py` | precomputed-matrix, label, parameter and seed checks |
| `core/registry.py` | name → class, taxonomy filters, capability shortlisting |
| `core/adapters.py` | adapting a third-party estimator to the contract |
| `core/tags.py` | `Capabilities.describe()`, which feeds the Sect. 8.2 table |
| `io/` | in-memory, CSV, Parquet and benchmark loading |
| `evaluation/protocol.py` | `Environment`, `Protocol`, `RunResult` |
| `evaluation/report.py` | both comparison tables, CSV and LaTeX export, cluster profiles |
| `pipeline/compose.py` | `ClusterPipeline` — a composition that *is* a clusterer |
| `viz/` | dendrograms, embeddings, selection curves, silhouettes, profiles |

The precomputed-matrix checks came first because the failures they catch — a similarity matrix passed as a dissimilarity, a squared distance, a non-zero diagonal — produce a plausible-looking partition rather than an error.

A component whose only content is a `_fit` override already passes scikit-learn's `check_estimator`. An adapted method needs only `_backend_import`, a parameter map and a capability declaration.

Still blocked, and on what:

- **`measures/validation/`** — the indices themselves. `ComparisonRun.run` and `best`, `selection/n_clusters.py` and `selection/stability.py` all wait on these.
- **`io/artifacts.py`** and `PersistableMixin` — a storage format decision.
- **`io/loaders/supabase.py`** — the Data Engineering team publishing its view.

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
