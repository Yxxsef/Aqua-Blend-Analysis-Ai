# Adding a preprocessing step

> **Status: derived from the contract, skeleton executed.** No custom
> preprocessor exists yet, but the `RobustClip` skeleton below was run
> end to end: it fits, transforms, passes `check_estimator`, reports through
> `describe_preprocessing`, and clusters inside a `make_cluster_pipeline`.
> **Correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Placement:
[CONTRIBUTING §2.2](../CONTRIBUTING.md#22-where-your-contribution-goes) — a
preprocessing step goes in `xxcluster/pipeline/preprocess.py`, and its
documentation counterpart is Sect. 3.3 rather than a template.

---

## First: do you need one?

**The concrete steps are scikit-learn transformers where suitable ones exist.**
`StandardScaler`, `SimpleImputer` and `OneHotEncoder` all drop straight into a
`ClusterPipeline` — they are `BaseEstimator` subclasses, which is the only
thing the pipeline requires.

Write a `BasePreprocessor` only when you need something scikit-learn does not
have, **or** when you need the two declarations below to be visible to the
reporting layer. Wrapping a scikit-learn transformer to add nothing is churn.

---

## Why this kind carries extra weight

There is no validation error to reveal a bad choice in unsupervised work.
`preprocess.py`'s own docstring names the three that matter, and they are worth
restating because your step will be one of them:

**Scaling.** Distance-based methods are not scale-invariant, so the choice of
scaler decides which features drive the partition. Left unscaled, turbidity in
NTU and pH contribute to a Euclidean distance in proportion to their units —
which is not a modelling decision anyone made.

**Missing values.** Imputation invents observations that will then be clustered
as if measured. An imputed value near a cluster boundary is a **fabricated
assignment**. The alternative — a dissimilarity defined on incomplete data, see
[dissimilarity-measure.md](dissimilarity-measure.md) — is worth preferring
wherever the method supports it.

**Categorical encoding.** One-hot encoding imposes a geometry in which every
pair of categories is equidistant. Where that is wrong, the encoding *is* the
problem and a mixed-type dissimilarity is the fix.

If your step is one of these three, the write-up in Sect. 3.3 must say what it
costs, not only what it does.

---

## Step 1 — The two declarations

```python
class BasePreprocessor(BaseTransformer, ABC):
    invertible: bool = True
    preserves_features: bool = True
```

### `invertible`

Whether the step can be undone.

`evaluation.report.profile_clusters` reports cluster profiles **in original
units** — that is what turns a partition into something the project can act on,
per Sect. 4.4. Doing so requires inverting the chain of steps back to the
measured features. A non-invertible step in the middle of a pipeline therefore
**costs interpretability**, and should be a decision rather than an accident.

Declare `False` honestly and say in Sect. 3.3 what interpretation is lost.

### `preserves_features`

Whether output columns still correspond to input features. `False` for any
reduction step, after which a feature-level interpretation is no longer
available.

If `False`, you **must** override `get_feature_names_out` — the base refuses:

```
NotImplementedError: <Class> does not preserve features, so it must name
its outputs itself.
```

That refusal is deliberate. After a step that does not preserve features, a
cluster profile can no longer be read in the measured variables, and the names
are the only record of what was lost.

---

## Step 2 — Skeleton

```python
class RobustClip(BasePreprocessor):
    """Clip each feature to a quantile range before scaling.

    <what it does, and what it costs — see Sect. 3.3>
    """

    invertible = False           # clipping loses the original extremes
    preserves_features = True

    def __init__(self, *, lower: float = 0.01, upper: float = 0.99) -> None:
        self.lower = lower
        self.upper = upper

    def _fit(self, X, y=None, **fit_params) -> None:
        self.lower_bounds_ = np.quantile(X, self.lower, axis=0)
        self.upper_bounds_ = np.quantile(X, self.upper, axis=0)

    def transform(self, X):
        ensure_fitted(self, "lower_bounds_")
        X = self._validate_input(X, reset=False)
        return np.clip(X, self.lower_bounds_, self.upper_bounds_)
```

Three things to get right:

- **Bounds are learned in `_fit`, not computed in `transform`.** Otherwise each
  call sees different data and the step is not a fitted transformation at all —
  and inside a resampling loop it leaks the held-out rows.
- **`reset=False` in `transform`.** It checks the new data against the recorded
  `n_features_in_` rather than overwriting it.
- **`TransformerMixin` gives you `fit_transform`** through `BaseTransformer`;
  do not write it.

---

## Step 3 — Verify, including in a pipeline

```bash
python -c "
import numpy as np
from sklearn.utils.estimator_checks import check_estimator
from xxcluster.pipeline.preprocess import <Class>, describe_preprocessing

X = np.random.default_rng(0).random((20, 4)) * [1, 100, 0.01, 5]
p = <Class>().fit(X)

print('transform    ', p.transform(X).shape)
print('names out    ', p.get_feature_names_out(['a','b','c','d']))
print('declared     ', p.invertible, p.preserves_features)
check_estimator(<Class>()); print('check_estimator PASSED')

# describe_preprocessing takes a *pipeline*, not a bare step -- a list of
# (name, step) pairs is enough
print(describe_preprocessing([('clip', p)]))
"
```

Then in the composition it will actually live in:

```bash
python -c "
import numpy as np
from xxcluster.pipeline.compose import make_cluster_pipeline
from xxcluster.pipeline.preprocess import <Class>
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans

X = np.random.default_rng(0).random((60, 4))
pipe = make_cluster_pipeline(<Class>(), KMeans(n_clusters=3))
print(pipe.fit(X).labels_[:10])
"
```

`ClusterPipeline` clones every step, so the instance you hand in is left as you
left it — and a step that mutates its parameters in `__init__` will fail here
first.

---

## Step 4 — Sect. 3.3, and the protocol

There is no template for this kind. Add a paragraph to
`documentation/sections/methodology.tex` under the preprocessing discussion,
naming:

1. what the step does,
2. **what it costs** — the fabricated assignments, the imposed geometry, the
   lost invertibility,
3. why the alternative was not taken.

Then decide whether it belongs in the **shared** pipeline:

```python
protocol = Protocol(preprocessing=make_cluster_pipeline(...), ...)
```

The shared pipeline is applied identically before every method, and
`ComparisonRun` fits it **once** and shares the result — so it is fixed in
Sect. 4.1 and never supplied per method. A method that needs a deviation
records it against itself, in its own *Application* paragraph, rather than
changing this.

`describe_preprocessing` is what puts your declarations into the report. Note
it returns `preserves_features: None` for a foreign transformer — unknown, not
false — which is the reason to write a `BasePreprocessor` when the distinction
matters.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `does not preserve features, so it must name its outputs itself` | `preserves_features = False` without overriding `get_feature_names_out` |
| Cluster profiles cannot be reported in original units | a non-invertible step mid-pipeline; declared, but its cost not accepted |
| Stability results are optimistic | statistics computed in `transform` rather than learned in `_fit`, leaking across the resampling boundary |
| `check_estimator` fails on `clone` | a parameter transformed in `__init__` |
| Scores differ between the notebook and `ComparisonRun` | preprocessing applied in one place and not the other — put it in the `Protocol`, not in the cell |
