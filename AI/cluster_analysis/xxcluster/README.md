# xxcluster

Cluster analysis for the AquaBlend dataset: the codebase behind `documentation/main.pdf`, *In Search of Cluster Analysis*.

The document and the package share one structure: a method's write-up and its implementation sit at matching addresses in the two trees, and docstrings cite the document by section number.

**Status: the contract and the family machinery work; one method exists.** K-Means is adapted from scikit-learn and passes `check_estimator`. The `cluster/` family base classes are implemented, so a native method now writes only its subfamily's hooks. No dimensionality reduction technique, validity index or dissimilarity measure exists yet.

| Area | What works |
|---|---|
| `core/base.py` | `fit` and the steps it runs; subclasses override only `_fit` |
| `cluster/partitional/base.py` | the restart loop: seeds per restart, best-by-criterion, derived `n_clusters_` |
| `cluster/partitional/sse_based/base.py` | `predict` and `transform` for any prototype method |
| `cluster/hierarchical/base.py` | `cut` by level or height, and `_fit`; `linkage_` / `children_` / `distances_` reconciled |
| `cluster/partitional/density_based/base.py` | estimate → extract → recount, with the `-1` convention enforced |
| `cluster/partitional/model_based/base.py` | `predict`, `predict_proba`, `score_samples`, `sample` |
| `core/validation.py` | precomputed-matrix, label, parameter and seed checks |
| `core/registry.py` | name → class, taxonomy filters, capability shortlisting |
| `core/adapters.py` | adapting a third-party estimator to the contract |
| `core/tags.py` | `Capabilities.describe()`, which feeds the Sect. 8.2 table |
| `io/` | in-memory, CSV, Parquet and benchmark loading |
| `evaluation/protocol.py` | `Environment`, `Protocol`, `RunResult` |
| `evaluation/report.py` | `ComparisonRun`, both comparison tables, CSV and LaTeX export, cluster profiles |
| `pipeline/compose.py` | `ClusterPipeline`, a composition that *is* a clusterer |
| `viz/` | dendrograms, embeddings, selection curves, silhouettes, profiles |

A component whose only content is a `_fit` override already passes scikit-learn's `check_estimator`. An adapted method needs only `_backend_import`, a parameter map and a capability declaration.

Still blocked, and on what:

- **`measures/`**: the indices and the dissimilarities themselves. `selection/n_clusters.py` and `selection/stability.py` wait on these, and `metric=` cannot dispatch to a named measure until one is registered.
- **`cluster/hierarchical/linkage.py`**: no criterion is implemented, so `linkage="ward"` resolves to nothing. The hierarchical family cannot produce a method until it is.
- **`dim_red/`**: `BaseLinearReducer.transform` / `inverse_transform` still raise, so Sect. 6 has nothing behind it.
- **`cluster/hybrid/`, `partitional/fuzzy/`, `partitional/graph_theoretic/`**: deliberately out of scope for the current block; their bases are untouched.
- **`io/artifacts.py`** and `PersistableMixin`: a storage format decision.
- **`io/loaders/supabase.py`**: the Data Engineering team publishing its view.

Nothing in `cluster/` is covered by a committed test: `tests/` is gitignored. That is the first task on the current list.

## Layout

| Directory | Holds | Document |
|---|---|---|
| `core/` | The contract: base classes, mixins, protocols, tags, registry | n/a |
| `cluster/` | Clustering methods, by family | Sect. 7 |
| `dim_red/` | Dimensionality reduction, intrinsic dimension | Sect. 6 |
| `measures/` | Dissimilarity measures and validity indices | Sect. 7.1–7.2 |
| `pipeline/` | Preprocessing steps and composition | Sect. 3.3 |
| `selection/` | Choosing \|C\|, stability analysis | Sect. 4.3 |
| `evaluation/` | The shared protocol, the comparison tables | Sect. 4, 8 |
| `io/` | Dataset loading, artefact storage | Sect. 3.1, App. A |
| `viz/` | Figures | n/a |
| `tasks/` | End-to-end analyses; the horizontal extension point | n/a |

`core/` depends on nothing else in the package; everything else depends on `core/`.

## The contract

Every component is a scikit-learn estimator, inheriting `BaseEstimator` through `core.base.BaseComponent`. Four rules (parameters, fitted state, the template method, and the capability declaration) with what each one buys: [ARCHITECTURE §3.1](ARCHITECTURE.md#31-the-estimator-interface).

## Install

```bash
pip install -r ../requirements.txt
```

Needs `numpy`, `scipy`, `scikit-learn`, `pandas`; `matplotlib` for `viz/`. Backends for adapted methods are optional and imported at fit time.

## Further reading

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: what each folder and file does, how a run flows through them, and where to extend.
- **[../CONTRIBUTING.md](../CONTRIBUTING.md)**: how to add a method to the code and its section to the document, and how to evidence it in a notebook.
