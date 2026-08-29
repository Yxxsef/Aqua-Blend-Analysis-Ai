# xxcluster: structure and design

What each folder holds, what each file is for, and how they work as one thing. For a summary see [README.md](README.md); for how to contribute to it see [../CONTRIBUTING.md](../CONTRIBUTING.md).

---

## 1. The idea in one paragraph

A clustering study is a comparison, and a comparison is only valid if every method is treated identically. So the package is built around a single contract: every method, measure, reducer and step is a scikit-learn estimator with the same interface, declaring what it assumes and what it supports. Once that holds, the surrounding machinery, i.e. preprocessing, choosing \|C\|, stability, scoring, plotting, reporting, can be written once and applied to everything, and adding a method means writing the method and nothing else.

## 2. Layering

```
                 tasks/                         end-to-end analyses
                    |
   +-----------+----+-------+--------+
   |           |            |        |
 pipeline/  selection/  evaluation/  viz/        machinery
   |           |            |        |
   +-----------+----+-------+--------+
                    |
      cluster/   dim_red/   measures/            components
                    |
                  core/                          the contract
                    |
                   io/                           data in, artefacts out
```

One rule: **`core/` imports nothing else from the package.** Everything else imports `core/`. An import from `core/` into a sibling is a design error as it would make the contract depend on an implementation of it.

Machinery layers depend on components only through `core/`'s base classes and protocols, never on a concrete method.

## 3. The contract

### 3.1 The estimator interface

```python
est = Method(n_clusters=3, metric="euclidean")   # params only, no work
est.fit(X)                                       # does the work
est.labels_                                      # fitted state
```

Four rules:

| Rule | Why |
|---|---|
| Params in `__init__` only, stored unmodified, not validated there | `get_params`/`set_params` round-trip; `clone` works, so restarts and sweeps are independent |
| Fitted state ends in `_`, absent until `fit` succeeds | Distinguishes request from result; `NotFittedError` becomes possible |
| Override `_fit`, never `fit` | Validation, bookkeeping and capability checks happen once, identically, for every method |
| Declare `_capabilities` | Consumed by the registry and by Sect. 8.2's table: declarations, not prose |

### 3.2 The fit lifecycle

`BaseComponent.fit` is a template method running a fixed sequence. **It is implemented** ([`core/base.py`](core/base.py)):

```
fit(X, y)
  ├─ _validate_params()      sklearn's constraints where declared
  ├─ _check_capabilities()   declaration must match the interface
  ├─ _validate_input(X)      feature matrix or precomputed; records n_features_in_
  ├─ _fit(X, y)              << the subclass writes only this >>
  └─ _check_fitted()         declared attributes must now exist
  return self
```

Each step earns its place by catching something that is otherwise silent:

| Step | Catches |
|---|---|
| `_validate_params` | An out-of-range parameter, via `_parameter_constraints` if the class declares one. Deferred from `__init__` so `clone` still works |
| `_check_capabilities` | A class declaring `is_inductive` with no `predict`, which would put a false row in Sect. 8.2's table |
| `_validate_input` | A similarity matrix passed where a dissimilarity is expected; NaN in a method that never declared `handles_missing` |
| `_check_fitted` | `_fit` setting `labels_` but forgetting `n_clusters_`; caught here, naming the omission, not three layers downstream in a report with a missing column |

`_required_fitted` is collected across the MRO, so a subfamily declares only what it adds: `BaseClusterer` requires `labels_` and `n_clusters_`, and a density-based subclass adding `_required_fitted = ("n_noise_",)` inherits both.

### 3.3 Component kinds

`core/base.py` defines one base class per kind of thing that can be fitted. The last three exist so the package extends sideways without reopening the contract:

| Base class | Interface | For |
|---|---|---|
| `BaseClusterer` | `fit` → `labels_`, `n_clusters_` | Clustering methods |
| `BaseTransformer` | `fit`, `transform` | Any representation change |
| `BaseDimReducer` | `+ embedding_`, `n_components_` | Dimensionality reduction |
| `BaseOutlierDetector` | `+ score_samples` | Anomaly detection (future) |
| `BaseGenerator` | `+ sample` | Scenario generation (future) |
| `BasePredictor` | `+ predict` | Supervised models (future) |

### 3.4 Capability mixins

Methods vary along axes that cut across the taxonomy, so those axes are mixins (`core/mixins.py`) rather than base classes: a class inherits one family base plus the capabilities it actually has, and no base class promises something its subclasses cannot do.

| Mixin | Adds | Only for methods that |
|---|---|---|
| `InductiveMixin` | `predict` | Can label observations unseen at fit time |
| `SoftAssignmentMixin` | `memberships_`, `predict_proba` | Assign by degree, not by label |
| `HierarchyMixin` | `linkage_`, `children_`, `cut` | Build a cuttable hierarchy |
| `NoiseAwareMixin` | `n_noise_`, label `-1` | May decline to assign an observation |
| `ProbabilisticMixin` | `score_samples`, `bic`, `aic` | Fit a likelihood |
| `PrecomputedMixin` | Accepts a square matrix as `X`, validated against a declared `PrecomputedKind` | Touch data only through `d(·,·)` or a similarity |
| `PersistableMixin` | `save`, `load` | Any component (opt-in) |

The mixin and the `_capabilities` declaration must agree; `_check_capabilities` enforces the pair.

`PrecomputedMixin` carries one further declaration, because "precomputed" does not mean one thing. A method states which `PrecomputedKind` it consumes and which parameter carries it, and the mixin dispatches to the matching check:

| Kind | Parameter | Rules | Used by |
|---|---|---|---|
| `DISSIMILARITY` | `metric` | zero diagonal, non-negative, symmetry optional (Def. 2) | hierarchical, density-based, manifold |
| `AFFINITY` | `affinity` | non-negative, symmetric, diagonal free | graph-theoretic |
| `KERNEL` | `kernel` | symmetric, non-negative diagonal, off-diagonal may be negative | kernel reducers |

Validating one as another is not a type error; it rejects valid input, or accepts invalid input and returns a wrong partition. The checks live in `core/validation.py` and nowhere else.

### 3.5 Native or adapted

The default is to adapt a mature implementation rather than reimplement it. An adapter (`core/adapters.py`) translates parameter names, copies fitted attributes onto ours, and fills in whatever the backend does not expose:

```python
@register("hdbscan")
class HDBSCAN(AdaptedClusterer, BaseDensityClusterer):
    _backend_import = "sklearn.cluster.HDBSCAN"
    _param_map = {"min_samples": "min_samples"}
    _capabilities = Capabilities(backend=Backend.SKLEARN, handles_noise=True, ...)
```

The adapter must come **first** in the bases, so the MRO reaches `AdaptedClusterer._fit` before the family base's. A family `_fit` is the native path (the partitional one runs the restart loop around `_fit_once`, the hierarchical one builds the tree and cuts it), and an adapted method implements none of those hooks, because its backend does the whole fit.

This is why **a hook that only a native fitting loop calls (`_fit_once`, `_update_centers`, `_build_hierarchy`, `_partition_graph`) is a concrete method raising `NotImplementedError`, never an `@abstractmethod`.** An adapted method never reaches one, so an abstract hook would make its whole subfamily impossible to adapt: `ABCMeta` refuses to instantiate the class. Only `_fit` stays abstract, and the adapters supply it. A hook every subclass must answer whichever route it took (`BaseHybridClusterer._check_steps`) does stay abstract.

Where a backend does not expose an attribute the contract declares, derive it in `_derive_missing`: `n_clusters_` and `n_noise_` are derived there already, and, say, a `converged_` flag that scikit-learn signals only by stopping early.

Write `_fit` natively where no good implementation exists, or where following the formulation in the document is the point. `_capabilities.backend` records which route was taken, so any result traces to the code that produced it.

---

## 4. The subpackages

### `core/`: the contract

| File | Holds |
|---|---|
| `base.py` | `BaseComponent` and the six kind-specific bases; the conventions |
| `mixins.py` | The seven capability mixins |
| `protocols.py` | Structural interfaces (`Clusterer`, `Dissimilarity`, …) for duck-typed objects |
| `tags.py` | `Capabilities`, the declaration dataclass |
| `types.py` | Type aliases; `Family`, `SubFamily`, `Backend`, `Assignment`, `ComponentKind`, `Scaling` |
| `registry.py` | `ComponentRegistry`, the global `REGISTRY`, the `@register` decorator |
| `adapters.py` | `BackendAdapter`, `AdaptedClusterer`, `AdaptedDimReducer` |
| `validation.py` | Input checks sklearn does not provide: the three precomputed-matrix kinds, labels, `n_clusters`, seeds, fitted state |
| `exceptions.py` | `XXClusterError` and its subclasses |

Base classes are how you *build* a component; protocols are how the machinery *accepts* one. The difference matters: an adapted third-party object satisfies `Clusterer` without inheriting anything of ours.

The registry turns a name into a class, so an experiment can be a list of strings in a notebook rather than a list of imports, and so a sweep can cover every registered method of a family without naming them.

### `cluster/`: clustering methods (Sect. 7)

Mirrors the document's taxonomy one directory per subsection.

| Path | Base class | Distinguishing contract |
|---|---|---|
| `hierarchical/base.py` | `BaseHierarchicalClusterer` | Fit builds the tree; `n_clusters` is a *cut*, not a fitting parameter |
| `hierarchical/agglomerative/` | `BaseAgglomerative` | Bottom-up merge loop; a method here is a linkage plus a declaration |
| `hierarchical/divisive/` | `BaseDivisive` | Top-down; two choices: which cluster to split, and how |
| `hierarchical/linkage.py` | `BaseLinkage` | Lifts `d(·,·)` on points to `d(·,·)` on clusters; shared by both directions |
| `partitional/base.py` | `BasePartitionalClusterer` | Iterative, converges locally, depends on initialisation, hence `n_init`, `tol`, `n_iter_`, `converged_` |
| `partitional/sse_based/` | `BasePrototypeClusterer` | `cluster_centers_`; inductive; subclasses differ only in `_update_centers` |
| `partitional/density_based/` | `BaseDensityClusterer` | \|C\| is a *result*; noise is `-1`; no `n_init` (does not iterate) |
| `partitional/model_based/` | `BaseModelBasedClusterer`, `BaseMixtureClusterer` | A fitted model; the mixture variant adds likelihood, BIC/AIC, `sample` |
| `partitional/graph_theoretic/` | `BaseGraphClusterer` | Build graph, then partition, with both stages exposed, because failures are usually in the first |
| `partitional/fuzzy/` | `BaseFuzzyClusterer` | `memberships_` plus the defuzzified `labels_`; the fuzzifier exponent |
| `hybrid/base.py` | `BaseHybridClusterer` | Holds constituents as params, so `get_params(deep=True)` reaches into them |

Reserved subfamily names (`subspace`, `search_based`, `miscellaneous`) are already in `SubFamily`; create the package when the first such method arrives.

### `dim_red/`: dimensionality reduction (Sect. 6)

| Path | Holds |
|---|---|
| `linear/base.py` | `BaseLinearReducer`: `components_`, `explained_variance_ratio_`, invertible, inductive |
| `nonlinear/base.py` | `BaseNonlinearReducer`: `embedding_`, `trustworthiness`; assumes only that the map is not a projection |
| ↳ | `BaseManifoldReducer`: neighbourhood-based, `stress_`, mostly transductive; the manifold hypothesis lives *here* |
| ↳ | `BaseKernelReducer`: kernel PCA and relatives; inductive, deterministic, spectral, no manifold assumed |
| `intrinsic_dim.py` | `BaseIntrinsicDimEstimator`, `manifold_hypothesis_report` |

**Nonlinear is not the same as manifold learning**, and the split above is the consequence. Kernel PCA is nonlinear yet inductive, deterministic, spectral, and takes a kernel matrix rather than a neighbourhood graph, so a base class asserting the manifold hypothesis would be wrong about it on every count. The document keeps the same distinction: Sect. 6.2 treats the manifold hypothesis as its own topic, Sect. 6.4 is the broader family.

The axis that matters most is **inductive vs transductive**. A linear map and a kernel map both apply to new points; most manifold learners embed only what they were fitted on. Only the former can precede a clustering step in a pipeline that will later see new data, so declaring it is not optional.

`intrinsic_dim.py` answers Objective 4 of the introduction (is the manifold hypothesis supported?) and gives a principled `n_components` instead of "2, because that plots".

### `measures/`: dissimilarity and validation (Sect. 7.1)

| Path | Holds |
|---|---|
| `dissimilarity/base.py` | `BaseDissimilarity`: `__call__`, `pairwise`, and declared properties (`is_metric`, `is_symmetric`, `accepts_missing`, …) |
| `validation/base.py` | `BaseValidityIndex`: `score`, `higher_is_better`, `handles_noise` |
| `validation/internal.py` | `BaseInternalIndex`: data + labels only, and the shape it implicitly rewards |
| `validation/external.py` | `BaseExternalIndex`: labels vs labels; also used for stability |
| `validation/relative.py` | `BaseRelativeCriterion`: selects among candidate partitions |

Two declarations do real work. `is_metric` (per Def. 1) gates methods whose correctness needs the triangle inequality: Ward's criterion, any distance-pruning acceleration. `higher_is_better` has no default, because an index whose direction is assumed is one that will eventually be compared the wrong way round.

An index is *defined* here and *applied* by `evaluation/`.

### `pipeline/`: preprocessing and composition (Sect. 3.3)

| File | Holds |
|---|---|
| `preprocess.py` | `BasePreprocessor` (`invertible`, `preserves_features`), `describe_preprocessing` |
| `compose.py` | `ClusterPipeline`, `make_cluster_pipeline` |

`ClusterPipeline` exists because sklearn's `Pipeline` cannot end in a clusterer: there is no `predict` to delegate to, and the output is `labels_`. Closing that gap makes a composition substitutable for a bare method everywhere, which is what keeps preprocessing *inside* the resampling loop; applied outside it, it leaks across folds and inflates stability.

`invertible` and `preserves_features` are about interpretation: cluster profiles are reported in original units, so a non-invertible step mid-pipeline costs interpretability and should be a decision, not an accident.

### `selection/`: choosing \|C\| and testing stability (Sect. 4.3)

| File | Holds |
|---|---|
| `base.py` | `BaseSelector`: wraps a method, sweeps candidates, exposes `best_params_` and full `results_` |
| `n_clusters.py` | `BaseNClustersSelector`: generate candidates, score, apply a relative criterion; keeps `curve_` and `conclusive_` |
| `stability.py` | `BasePerturbation`, `StabilityAnalysis`: refit under perturbation, score agreement |

Without labels there is no held-out error, so selection rests on two substitutes: a criterion curve, and reproducibility under perturbation. They answer different questions, and **a partition that is optimal by the first and unstable under the second is not a finding.**

A selector is itself a component, so the search it performed travels with the result instead of living in a notebook.

### `evaluation/`: protocol and comparison (Sect. 4, 8)

| File | Holds |
|---|---|
| `protocol.py` | `Protocol` (indices, restarts, seeds, preprocessing), `Environment.capture()`, `RunResult` |
| `report.py` | `ComparisonRun`, `ComparisonTable`, `profile_clusters` |

`Protocol` is the setup fixed once and applied to every method; no method supplies its own, which is what makes Sect. 8 a comparison rather than a collection. `Environment.capture()` records versions and revision at run time, satisfying App. A without a hand-maintained list.

`ComparisonTable.quantitative()` renders Sect. 8.1 from the scores; `.qualitative()` renders Sect. 8.2 from the `_capabilities` declarations. The second is why tags exist: a table maintained by hand in LaTeX drifts the moment a method changes; generated from declarations, it cannot. `.to_latex()` means a number reaches the document without being retyped.

`profile_clusters` reads the *original* features: it is the input to naming a regime (Sect. 4.4), so a scaled or reduced representation would be useless.

### `io/`: data in, artefacts out

| File | Holds |
|---|---|
| `datasets.py` | `FeatureSpec`, `Dataset`, `BaseDatasetLoader` (**implemented**) |
| `loaders/` | One loader per source: `FrameLoader`, `CsvLoader`, `ParquetLoader`, `BenchmarkLoader` (**implemented**); `supabase.py` awaits the published view |
| `artifacts.py` | `ArtifactMeta`, `BaseArtifactStore` (declared) |

Nothing else in the package reads a file or knows a path. A method receives an array, hence testable on synthetic data; a loader knows the AquaBlend schema, and is the only thing that does.

`FeatureSpec.role` separates columns clustered *on* from columns held back to *interpret with*. Clustering on a column and then explaining the clusters by it is circular, and the role field is what prevents it. Roles are **declared, never inferred**: a loader without a schema is refused, because no source can tell you which of its columns is a modelling input.

`BaseDatasetLoader.load` is a template method like `BaseComponent.fit`: subclasses implement `_read`, and inherit schema validation that no loader can skip. A missing column and an undeclared extra column are both errors: the first breaks the analysis, the second means the source changed and nobody recorded it.

The upstream store is live, so a result records the **window** its data covers rather than a copy of the rows: `provenance["data_cutoff"]`, rendered by `Dataset.provenance_statement()` into Sect. 3.1. Results are comparable within one cutoff; a later cutoff is a new dataset, and a difference in the numbers is then attributable. `check_ranges()` makes `valid_range` enforceable: values outside it are data faults to raise with the owning team, not outliers to cluster.

`ArtifactMeta` is a required argument to `save`, not an optional one: metadata written at the same moment as the result is provenance; written afterwards from memory, it is a description.

Upstream data is owned by the Data Engineering team. A data problem found here is raised with them, not patched here where the patch would be invisible.

### `viz/`: figures

| File | Holds |
|---|---|
| `dendrogram.py` | `plot_dendrogram`, `plot_merge_heights` |
| `embedding.py` | `plot_embedding`, `plot_component_loadings`, `plot_feature_pairs` |
| `diagnostics.py` | `plot_selection_curve`, `plot_silhouette`, `plot_stability`, `plot_cluster_profiles` |

Every function takes fitted results and fits nothing itself, because a routine that quietly refits plots something other than the result under discussion.

`plot_embedding` carries an explicit warning in its module: separation in a nonlinear embedding is not evidence of separation in the data, because the embedding was optimised to produce it. Hence the reporting rules (technique, parameters, seed and trustworthiness on the figure) and hence `plot_feature_pairs`, the check that a partition is visible in measured variables.

### `tasks/`: end-to-end analyses

| File | Holds |
|---|---|
| `base.py` | `BaseTask`, `TaskResult` (runs, figures, tables, **caveats**) |

A task composes components; it does not implement algorithms. Anything reusable belongs in the subpackage for its kind, where the registry and the comparison can reach it; a component defined inside a task is invisible to both.

`TaskResult.caveats` is deliberate: an inconclusive selection or an unstable partition is part of the output, not something filtered out of it.

---

## 5. How a comparison flows

**This is not what a notebook does.** A notebook evidences *one* implementation against its own write-up; see [CONTRIBUTING Part 3](../CONTRIBUTING.md#part-3-the-notebooks) for that procedure. What follows is the cross-notebook run that produces Sect. 8, and it happens **once, after those sections and notebooks are final**.

The unit of comparison is a **configuration**, not a method. Sect. 8 sets `KMeans` beside `PCA → KMeans` and `UMAP → HDBSCAN`, so every entry is a `ClusterPipeline` and a bare method is simply the one-step case.

```
io.datasets.Dataset          load once; every configuration sees the same data
        │
evaluation.Protocol          indices, restarts, seeds, shared preprocessing:
        │                    fixed here, never supplied per method
        │
pipeline.ClusterPipeline     one per configuration: [reduction →] method, as a
        │                    single component, so preprocessing stays inside
        │                    the resampling loop below
        │
selection.BaseSelector       sweep |C| or density params → best_params_, curve_
selection.StabilityAnalysis  refit under perturbation → stability_
        │                    both per configuration; a reduction changes them
        │
evaluation.ComparisonRun     every configuration, one Protocol → list[RunResult]
        │                    a failure is recorded, never dropped
        │
        ├── measures.validation           indices applied identically
        ├── evaluation.profile_clusters   clusters in original units
        ├── viz.*                       → figures, with provenance
        │
evaluation.ComparisonTable   → Sect. 8.1 (scores) and 8.2 (capabilities)
io.artifacts                 → stored with Protocol + Environment
```

Each stage consumes the contract and none of them knows which method it holds.

**The two tables aggregate at different granularity, and Sect. 8 must say which it is showing.** `quantitative()` is per configuration: `PCA → KMeans` scoring differently from `KMeans` is the finding, and the reduction has to be visible in the row. `qualitative()` is per *method*: capabilities are declared by a class, and a pipeline has none of its own, so a configuration's row there is its final method's row. Naming a configuration `kmeans` when a reduction preceded it puts a false row in both.

## 6. Where to extend

**Vertically: a new method.** One module under the matching subfamily, subclassing that subfamily's base, plus a `@register` line. Selection, evaluation and reporting find it through the registry; nothing else changes.

**Horizontally: a new task.** Time-series clustering, anomaly detection, scenario generation, demand forecasting. A subpackage under `tasks/`, plus whatever components it needs *in their own subpackages*: a series dissimilarity in `measures/dissimilarity/`, a detector on `BaseOutlierDetector`, a generator on `BaseGenerator`.

Time-series clustering illustrates the payoff of routing everything through `d(·,·)`: it needs a new dissimilarity and a representation step, and reuses every clustering method unchanged.

## 7. Conventions

- Notation follows the document's table: `m` observations, `n` features, `|C|` clusters, `d(·,·)` dissimilarity. Array shapes in docstrings use it: a feature matrix is `(m, n)`, a dissimilarity matrix `(m, m)`.
- scikit-learn's own names for those axes (`n_samples`, `n_features_in_`) are API, not notation, and keep their spelling.
- Noise is `-1`, everywhere.
- `n_clusters` is a request; `n_clusters_` is a result.
- Registered names are permanent, because they appear in artefacts and in the document's tables.
- Docstrings cite the document by section and literature by `literature.bib` key.
- `from __future__ import annotations` at the top of every module.
- `@abstractmethod` bodies are `...`; a concrete method not yet written raises `NotImplementedError`. Note that a `NotImplementedError` is not always a gap: it is also how a component refuses something it genuinely cannot do: a transductive technique asked to map unseen data, a nonlinear embedding asked for feature loadings. The docstring says which.

What is implemented and what is still blocked is in [README.md](README.md); it changes, and one list is easier to keep true than two.
