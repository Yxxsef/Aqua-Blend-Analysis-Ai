# Adding an internal validity index

> **Status: verified.** Carried out for Silhouette; the published-value check below was run against this repository and returns `0.5528`.

**Read [00-the-contract.md](00-the-contract.md) first.** Pairing table: [CONTRIBUTING §2.5](../CONTRIBUTING.md#25-adding-a-measure).

**File:** `xxcluster/measures/validation/internal.py`; append to it. The module and `BaseInternalIndex` already exist; one file holds the group.

An internal index scores **one partition using the data and the labels alone**, with no reference labelling. Silhouette, Calinski–Harabasz, Davies–Bouldin.

---

## An index is not a `BaseComponent`

`BaseValidityIndex` derives from `ABC`, not from `BaseComponent`. It is not fitted and holds no state beyond its configuration, so the estimator contract would add nothing. Consequences:

- No `fit`, no `_fit`, no `_required_fitted`, no trailing-underscore state.
- No `_capabilities`: an index declares its properties as **plain class attributes** instead.
- It is still registered, so it can be named in a `Protocol`.
- `_kind` comes from `BaseValidityIndex`, so `@register("name")` is complete.

---

## Step 1: Declare the properties

```python
class BaseInternalIndex(BaseValidityIndex, ABC):
    requires_labels_true = False    # inherited, do not restate
    requires_X = True               # inherited
    assumes_shape: str | None = None
```

| Attribute | Meaning | Document paragraph |
|---|---|---|
| `name` | Registry key **and** column heading in Sect. 8.1. Permanent. | n/a |
| `higher_is_better` | **Required, no default.** | 3. Properties |
| `range_` | Attainable range where bounded, e.g. `(-1.0, 1.0)` | 3. Properties |
| `handles_noise` | Whether the index is defined when observations are labelled `-1` | 4. Applicability |
| `assumes_shape` | The cluster geometry the index rewards | 7. Behaviour |
| `requires_labels_true`, `requires_X` | Inherited from `BaseInternalIndex` | 4. Applicability |

### `higher_is_better` has no default, deliberately

An index whose direction is assumed is one that will eventually be compared the wrong way round, which **inverts a conclusion** rather than breaking a test. Davies–Bouldin is minimised; Silhouette and Calinski–Harabasz are maximised. Get this wrong and `ComparisonRun.best` silently returns the worst method.

### `assumes_shape` is not decoration

Every index in this group formalises the same intuition (compact clusters, well separated), so every one of them encodes a notion of cluster *shape*. An index built on distances to a centroid rewards the compact, isotropic clusters the SSE family produces and penalises the elongated ones a density-based method is designed to find.

Used to rank methods from different families, such an index **does not rank them neutrally**. That is a threat to validity for Sect. 4.5, not a detail, and `internal.py`'s module docstring requires the caveat in every class docstring in the group.

### `handles_noise`, and act on it

Most internal indices are undefined for an observation in no cluster. Declaring `handles_noise = False` is only half the job; your `score` must enforce it:

```python
labels = check_labels(labels, allow_noise=self.handles_noise)
```

That way a caller scoring a DBSCAN result gets an error naming the problem, instead of a number that silently treats noise as a cluster of its own, which flatters the density method by scoring only the points it was confident about.

---

## Step 2: Implement `score`

The signature is uniform across all three index groups so the evaluation harness can call any index the same way. Consume what you declare and ignore the rest.

```python
@register("davies_bouldin")
class DaviesBouldin(BaseInternalIndex):
    """<one paragraph: what it measures, citing ref_<n>>

    <the assumes_shape caveat, in prose>

    Applied per Sect. 4.2.
    """

    name = "davies_bouldin"
    higher_is_better = False          # minimised
    range_ = (0.0, None)
    handles_noise = False
    assumes_shape = "compact, isotropic"

    def score(self, X=None, labels=None, *, labels_true=None,
              metric="euclidean", **kwargs) -> float:
        labels = check_labels(labels, allow_noise=self.handles_noise)
        if len(set(labels)) < 2:
            raise ValueError(
                f"{self.name} needs at least two clusters; got "
                f"{len(set(labels))}."
            )
        from sklearn.metrics import davies_bouldin_score
        return float(davies_bouldin_score(X, labels))
```

**Import the backend inside `score`,** as above; it keeps `import xxcluster` free of the dependency and matches how the adapters behave.

**Do not default `metric` away.** `BaseValidityIndex.score` says it must be the same measure the method was fitted with: K-Means determines clusters by Euclidean distance, so its validity must be Euclidean too. `metric` also accepts a precomputed dissimilarity matrix, which is the route for a mixed-type measure.

**Return a real `float`.** A numpy scalar propagates its dtype into the report tables and into `to_latex`'s integrality test.

You inherit two things for free:

- `__call__`: an alias for `score`, so your index can stand in wherever scikit-learn expects a scoring function.
- `is_better(a, b)`: the single place direction is applied, and NaN-safe; a NaN never wins, which is what lets a failed run be folded into a comparison and lose rather than propagate.

---

## Step 3: Register and verify

```python
@register("davies_bouldin")     # kind comes from BaseValidityIndex._kind
```

```bash
python -c "
from sklearn.datasets import load_iris
from sklearn.cluster import KMeans
from xxcluster.measures.validation.internal import <Class>
import numpy as np

X = load_iris().data
labels = KMeans(3, n_init=10, random_state=0).fit_predict(X)
idx = <Class>()

print('score       ', idx.score(X, labels))
print('direction   ', idx.is_better(0.55, 0.41))
print('callable    ', idx(X, labels))

noisy = labels.copy(); noisy[:5] = -1
try:
    idx.score(X, noisy)
    print('noise       ACCEPTED: is that what you declared?')
except ValueError as e:
    print('noise       refused:', str(e)[:60])
"
```

Then check it reaches the reporting layer:

```bash
python -c "
import xxcluster.measures.validation.internal
from xxcluster.core.registry import REGISTRY
from xxcluster.core.types import ComponentKind
print(REGISTRY.names(kind=ComponentKind.VALIDITY_INDEX))
"
```

### The check that makes this evidence

Where your index has a published value on a benchmark dataset, **assert it**:

```python
assert abs(Silhouette().score(X, labels) - 0.5528) < 1e-3
```

Silhouette on iris at |C|=3 is `0.5528`. Asserting it is what turns "my implementation ran" into "my implementation agrees with the literature", which is what `BenchmarkLoader` exists for. Put this in your notebook, not only here.

---

## Step 4: Write-up

`template/measure_template.tex` into `documentation/sections/clustering_methods/validity/<nn>-<name>.tex`. Labels `sec:measure:<name>:*`. Paragraph 3 is `higher_is_better`/`range_`, paragraph 4 is the applicability flags, paragraph 7 is `assumes_shape`.

Then [notebook.md](notebook.md). An index notebook needs a method to score, so in practice it pairs with one; say so explicitly in §2 Scope rather than leaving it implied.

---

## How your index gets used

Once registered, it is named as a string in a `Protocol` and applied to every method identically:

```python
protocol = Protocol(indices=["silhouette", "davies_bouldin"], random_state=42)
results = ComparisonRun(["kmeans", "dbscan"], protocol=protocol).run(X)
```

Two behaviours to know:

- **A misspelt name raises immediately**, before anything is fitted.
- **If your index refuses a result** (noise it cannot read, fewer than two clusters), `ComparisonRun` records NaN for that index alone and keeps the run's other scores. NaN renders as `--` in the LaTeX table and loses `is_better`. So raising a clear `ValueError` is the right behaviour; it does not sabotage the comparison.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `best()` returns the worst method | `higher_is_better` is backwards |
| A DBSCAN result scores fine but the number is meaningless | `handles_noise=False` declared but `check_labels(allow_noise=...)` not passed |
| `AttributeError: higher_is_better` | not declared; there is no default by design |
| The index column is missing from Sect. 8.1 | the module was never imported, so it never registered |
| Two methods from different families ranked confidently | `assumes_shape` caveat missing from §10 and Sect. 4.5 |
