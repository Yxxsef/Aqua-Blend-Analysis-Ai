# xxcluster — structure and design

What each folder holds, what each file is for, and how they work as one thing.
For a summary see [README.md](README.md); for how to add to it see
[../CONTRIBUTING.md](../CONTRIBUTING.md).

---

## 1. The idea in one paragraph

A clustering study is a comparison, and a comparison is only valid if every
method is treated identically. So the package is built around a single
contract: every method, measure, reducer and step is a scikit-learn estimator
with the same interface, declaring what it assumes and what it supports. Once
that holds, the surrounding machinery — preprocessing, choosing \|C\|,
stability, scoring, plotting, reporting — can be written once and applied to
everything, and adding a method means writing the method and nothing else.

## 2. Layering

```
                 tasks/          end-to-end analyses
                    |
   +--------+-------+-------+--------+
   |        |               |        |
 pipeline/  selection/  evaluation/  viz/        machinery
   |        |               |        |
   +--------+-------+-------+--------+
                    |
      cluster/   dim_red/   measures/            components
                    |
                  core/                          the contract
                    |
                   io/                           data in, artefacts out
```

One rule: **`core/` imports nothing else from the package.** Everything else
imports `core/`. An import from `core/` into a sibling is a design error — it
would make the contract depend on an implementation of it.

Machinery layers depend on components only through `core/`'s base classes and
protocols, never on a concrete method. That is what lets `evaluation/` score a
method written next year.

## 3. The contract

### 3.1 The estimator interface

```python
est = Method(n_clusters=3, metric="euclidean")   # params only, no work
est.fit(X)                                       # does the work
est.labels_                                      # fitted state
```

Four rules, all mechanically checkable:

| Rule | Why |
|---|---|
| Params in `__init__` only, stored unmodified, not validated there | `get_params`/`set_params` round-trip; `clone` works, so restarts and sweeps are independent |
| Fitted state ends in `_`, absent until `fit` succeeds | Distinguishes request from result; `NotFittedError` becomes possible |
| Override `_fit`, never `fit` | Validation, bookkeeping and capability checks happen once, identically, for every method |
| Declare `_capabilities` | Consumed by the registry and by Sect. 8.2's table — declarations, not prose |

### 3.2 The fit lifecycle

`BaseComponent.fit` is a template method running a fixed sequence:

```
fit(X, y)
  ├─ _validate_params()      constructor params, deferred from __init__
  ├─ _check_capabilities()   declaration must match the interface
  ├─ check_matrix(X)         validate input; record n_features_in_
  ├─ _fit(X, y)              << the subclass writes only this >>
  └─ verify declared fitted attributes were set
```

A subclass that sets `labels_` but not `n_clusters_` fails at the last step
rather than three layers downstream.

### 3.3 Component kinds

`core/base.py` defines one base class per kind of thing that can be fitted.
The last three exist so the package extends sideways without reopening the
contract:

| Base class | Interface | For |
|---|---|---|
| `BaseClusterer` | `fit` → `labels_`, `n_clusters_` | Clustering methods |
| `BaseTransformer` | `fit`, `transform` | Any representation change |
| `BaseDimReducer` | `+ embedding_`, `n_components_` | Dimensionality reduction |
| `BaseOutlierDetector` | `+ score_samples` | Anomaly detection (future) |
| `BaseGenerator` | `+ sample` | Scenario generation (future) |
| `BasePredictor` | `+ predict` | Supervised models (future) |

### 3.4 Capability mixins

Methods vary along axes that cut across the taxonomy, so those axes are
mixins (`core/mixins.py`) rather than base classes — a class inherits one
family base plus the capabilities it actually has, and no base class promises
something its subclasses cannot do.

| Mixin | Adds | Only for methods that |
|---|---|---|
| `InductiveMixin` | `predict` | Can label observations unseen at fit time |
| `SoftAssignmentMixin` | `memberships_`, `predict_proba` | Assign by degree, not by label |
| `HierarchyMixin` | `linkage_`, `children_`, `cut` | Build a cuttable hierarchy |
| `NoiseAwareMixin` | `n_noise_`, label `-1` | May decline to assign an observation |
| `ProbabilisticMixin` | `score_samples`, `bic`, `aic` | Fit a likelihood |
| `PrecomputedMixin` | Accepts a dissimilarity matrix as `X` | Touch data only through `d(·,·)` |
| `PersistableMixin` | `save`, `load` | — (opt-in) |

The mixin and the `_capabilities` declaration must agree; `_check_capabilities`
enforces the pair.

### 3.5 Native or adapted

The default is to adapt a mature implementation rather than reimplement it.
An adapter (`core/adapters.py`) translates parameter names, copies fitted
attributes onto ours, and fills in whatever the backend does not expose:

```python
@register("hdbscan")
class HDBSCAN(AdaptedClusterer, BaseDensityClusterer):
    _backend_import = "sklearn.cluster.HDBSCAN"
    _param_map = {"min_samples": "min_samples"}
    _capabilities = Capabilities(backend=Backend.SKLEARN, handles_noise=True, ...)
```

Write `_fit` natively where no good implementation exists, or where following
the formulation in the document is the point. `_capabilities.backend` records
which route was taken, so any result traces to the code that produced it.

---

## 4. The subpackages

### `core/` — the contract

| File | Holds |
|---|---|
| `base.py` | `BaseComponent` and the six kind-specific bases; the conventions |
| `mixins.py` | The seven capability mixins |
| `protocols.py` | Structural interfaces (`Clusterer`, `Dissimilarity`, …) for duck-typed objects |
| `tags.py` | `Capabilities` — the declaration dataclass |
| `types.py` | Type aliases; `Family`, `SubFamily`, `Backend`, `Assignment`, `ComponentKind`, `Scaling` |
| `registry.py` | `ComponentRegistry`, the global `REGISTRY`, the `@register` decorator |
| `adapters.py` | `BackendAdapter`, `AdaptedClusterer`, `AdaptedDimReducer` |
| `validation.py` | Input checks sklearn does not provide (dissimilarity matrices, label vectors) |
| `exceptions.py` | `XXClusterError` and its subclasses |

Base classes are how you *build* a component; protocols are how the machinery
*accepts* one. The difference matters: an adapted third-party object satisfies
`Clusterer` without inheriting anything of ours.

The registry turns a name into a class, so an experiment can be a list of
strings in a notebook rather than a list of imports — and so a sweep can cover
every registered method of a family without naming them.

### `cluster/` — clustering methods (Sect. 7)

Mirrors the document's taxonomy one directory per subsection.

| Path | Base class | Distinguishing contract |
|---|---|---|
| `hierarchical/base.py` | `BaseHierarchicalClusterer` | Fit builds the tree; `n_clusters` is a *cut*, not a fitting parameter |
| `hierarchical/agglomerative.py` | `BaseAgglomerative` | Bottom-up merge loop; a method here is a linkage plus a declaration |
| `hierarchical/divisive.py` | `BaseDivisive` | Top-down; two choices — which cluster to split, and how |
| `hierarchical/linkage.py` | `BaseLinkage` | Lifts `d(·,·)` on points to `d(·,·)` on clusters; shared by both directions |
| `partitional/base.py` | `BasePartitionalClusterer` | Iterative, converges locally, depends on initialisation — hence `n_init`, `tol`, `n_iter_`, `converged_` |
| `partitional/sse_based/` | `BasePrototypeClusterer` | `cluster_centers_`; inductive; subclasses differ only in `_update_centers` |
| `partitional/density_based/` | `BaseDensityClusterer` | \|C\| is a *result*; noise is `-1`; no `n_init` (does not iterate) |
| `partitional/model_based/` | `BaseModelBasedClusterer`, `BaseMixtureClusterer` | A fitted model; the mixture variant adds likelihood, BIC/AIC, `sample` |
| `partitional/graph_theoretic/` | `BaseGraphClusterer` | Build graph, then partition — both stages exposed, because failures are usually in the first |
| `partitional/fuzzy/` | `BaseFuzzyClusterer` | `memberships_` plus the defuzzified `labels_`; the fuzzifier exponent |
| `hybrid/base.py` | `BaseHybridClusterer` | Holds constituents as params, so `get_params(deep=True)` reaches into them |

Reserved subfamily names — `subspace`, `search_based`, `miscellaneous` — are
already in `SubFamily`; create the package when the first such method arrives.

### `dim_red/` — dimensionality reduction (Sect. 6)

| Path | Holds |
|---|---|
| `linear/base.py` | `BaseLinearReducer`: `components_`, `explained_variance_ratio_`, invertible, inductive |
| `nonlinear/base.py` | `BaseManifoldReducer`: `embedding_`, `stress_`, `trustworthiness`; transductive by default |
| `intrinsic_dim.py` | `BaseIntrinsicDimEstimator`, `manifold_hypothesis_report` |

The axis that matters is **inductive vs transductive**. A linear map applies to
new points; most manifold learners embed only what they were fitted on. Only
the former can precede a clustering step in a pipeline that will later see new
data, so declaring it is not optional.

`intrinsic_dim.py` answers Objective 4 of the introduction — is the manifold
hypothesis supported? — and gives a principled `n_components` instead of "2,
because that plots".

### `measures/` — dissimilarity and validation (Sect. 7.1)

| Path | Holds |
|---|---|
| `dissimilarity/base.py` | `BaseDissimilarity`: `__call__`, `pairwise`, and declared properties (`is_metric`, `is_symmetric`, `accepts_missing`, …) |
| `validation/base.py` | `BaseValidityIndex`: `score`, `higher_is_better`, `handles_noise` |
| `validation/internal.py` | `BaseInternalIndex` — data + labels only, and the shape it implicitly rewards |
| `validation/external.py` | `BaseExternalIndex` — labels vs labels; also used for stability |
| `validation/relative.py` | `BaseRelativeCriterion` — selects among candidate partitions |

Two declarations do real work. `is_metric` (per Def. 1) gates methods whose
correctness needs the triangle inequality — Ward's criterion, any
distance-pruning acceleration. `higher_is_better` has no default, because an
index whose direction is assumed is one that will eventually be compared the
wrong way round.

An index is *defined* here and *applied* by `evaluation/`.

### `pipeline/` — preprocessing and composition (Sect. 3.3)

| File | Holds |
|---|---|
| `preprocess.py` | `BasePreprocessor` (`invertible`, `preserves_features`), `describe_preprocessing` |
| `compose.py` | `ClusterPipeline`, `make_cluster_pipeline` |

`ClusterPipeline` exists because sklearn's `Pipeline` cannot end in a clusterer
— there is no `predict` to delegate to, and the output is `labels_`. Closing
that gap makes a composition substitutable for a bare method everywhere, which
is what keeps preprocessing *inside* the resampling loop; applied outside it,
it leaks across folds and inflates stability.

`invertible` and `preserves_features` are about interpretation: cluster
profiles are reported in original units, so a non-invertible step mid-pipeline
costs interpretability and should be a decision, not an accident.

### `selection/` — choosing \|C\| and testing stability (Sect. 4.3)

| File | Holds |
|---|---|
| `base.py` | `BaseSelector` — wraps a method, sweeps candidates, exposes `best_params_` and full `results_` |
| `n_clusters.py` | `BaseNClustersSelector` — generate candidates, score, apply a relative criterion; keeps `curve_` and `conclusive_` |
| `stability.py` | `BasePerturbation`, `StabilityAnalysis` — refit under perturbation, score agreement |

Without labels there is no held-out error, so selection rests on two
substitutes: a criterion curve, and reproducibility under perturbation. They
answer different questions, and **a partition that is optimal by the first and
unstable under the second is not a finding.**

A selector is itself a component, so the search it performed travels with the
result instead of living in a notebook.

### `evaluation/` — protocol and comparison (Sect. 4, 8)

| File | Holds |
|---|---|
| `protocol.py` | `Protocol` (indices, restarts, seeds, preprocessing), `Environment.capture()`, `RunResult` |
| `report.py` | `ComparisonRun`, `ComparisonTable`, `profile_clusters` |

`Protocol` is the setup fixed once and applied to every method — no method
supplies its own, which is what makes Sect. 8 a comparison rather than a
collection. `Environment.capture()` records versions and revision at run time,
satisfying App. A without a hand-maintained list.

`ComparisonTable.quantitative()` renders Sect. 8.1 from the scores;
`.qualitative()` renders Sect. 8.2 from the `_capabilities` declarations. The
second is why tags exist: a table maintained by hand in LaTeX drifts the moment
a method changes; generated from declarations, it cannot. `.to_latex()` means a
number reaches the document without being retyped.

`profile_clusters` reads the *original* features — it is the input to naming a
regime (Sect. 4.4), so a scaled or reduced representation would be useless.

### `io/` — data in, artefacts out

| File | Holds |
|---|---|
| `datasets.py` | `FeatureSpec`, `Dataset`, `BaseDatasetLoader` |
| `artifacts.py` | `ArtifactMeta`, `BaseArtifactStore` |

Nothing else in the package reads a file or knows a path. A method receives an
array — hence testable on synthetic data; a loader knows the AquaBlend schema —
and is the only thing that does.

`FeatureSpec.role` separates columns clustered *on* from columns held back to
*interpret with*. Clustering on a column and then explaining the clusters by it
is circular, and the role field is what prevents it.

`ArtifactMeta` is a required argument to `save`, not an optional one: metadata
written at the same moment as the result is provenance; written afterwards from
memory, it is a description.

Upstream data is owned by the Data Engineering team. A data problem found here
is raised with them, not patched here where the patch would be invisible.

### `viz/` — figures

| File | Holds |
|---|---|
| `dendrogram.py` | `plot_dendrogram`, `plot_merge_heights` |
| `embedding.py` | `plot_embedding`, `plot_component_loadings`, `plot_feature_pairs` |
| `diagnostics.py` | `plot_selection_curve`, `plot_silhouette`, `plot_stability`, `plot_cluster_profiles` |

Every function takes fitted results and fits nothing itself — a routine that
quietly refits plots something other than the result under discussion.

`plot_embedding` carries an explicit warning in its module: separation in a
nonlinear embedding is not evidence of separation in the data, because the
embedding was optimised to produce it. Hence the reporting rules — technique,
parameters, seed and trustworthiness on the figure — and hence
`plot_feature_pairs`, the check that a partition is visible in measured
variables.

### `tasks/` — end-to-end analyses

| File | Holds |
|---|---|
| `base.py` | `BaseTask`, `TaskResult` (runs, figures, tables, **caveats**) |

A task composes components; it does not implement algorithms. Anything
reusable belongs in the subpackage for its kind, where the registry and the
comparison can reach it — a component defined inside a task is invisible to
both.

`TaskResult.caveats` is deliberate: an inconclusive selection or an unstable
partition is part of the output, not something filtered out of it.

---

## 5. How a run flows

```
io.datasets.Dataset          load; features carry roles and units
        │
pipeline.ClusterPipeline     preprocess → method, as one component
        │
selection.BaseSelector       sweep |C| or density params → best_params_, curve_
selection.StabilityAnalysis  refit under perturbation → stability_
        │
evaluation.ComparisonRun     every method, one Protocol → list[RunResult]
        │
        ├── measures.validation      indices applied identically
        ├── evaluation.profile_clusters   clusters in original units
        │
evaluation.ComparisonTable   → Sect. 8.1 (scores) and 8.2 (capabilities)
viz.*                        → figures, with provenance
io.artifacts                 → stored with Protocol + Environment
```

Each stage consumes the contract and none of them knows which method it holds.

## 6. Where to extend

**Vertically — a new method.** One module under the matching subfamily,
subclassing that subfamily's base, plus a `@register` line. Selection,
evaluation and reporting find it through the registry; nothing else changes.

**Horizontally — a new task.** Time-series clustering, anomaly detection,
scenario generation, demand forecasting. A subpackage under `tasks/`, plus
whatever components it needs *in their own subpackages*: a series
dissimilarity in `measures/dissimilarity/`, a detector on
`BaseOutlierDetector`, a generator on `BaseGenerator`.

Time-series clustering illustrates the payoff of routing everything through
`d(·,·)`: it needs a new dissimilarity and a representation step, and reuses
every clustering method unchanged.

## 7. Conventions

- Notation follows the document's table: `m` observations, `n` features,
  `|C|` clusters, `d(·,·)` dissimilarity. Array shapes in docstrings use it —
  a feature matrix is `(m, n)`, a dissimilarity matrix `(m, m)`.
- scikit-learn's own names for those axes (`n_samples`, `n_features_in_`) are
  API, not notation, and keep their spelling.
- Noise is `-1`, everywhere.
- `n_clusters` is a request; `n_clusters_` is a result.
- Registered names are permanent — they appear in artefacts and in the
  document's tables.
- Docstrings cite the document by section and literature by `literature.bib`
  key.
- `from __future__ import annotations` at the top of every module.
- In the skeleton: `@abstractmethod` bodies are `...`; unwritten concrete
  methods raise `NotImplementedError`.
