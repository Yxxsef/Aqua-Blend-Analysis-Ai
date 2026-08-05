# Adding a dissimilarity measure

> **Status: derived from the contract.** No measure exists yet. `BaseDissimilarity` and `PrecomputedMixin` were read directly, and the skeleton below was **executed**: a Euclidean stand-in fits, returns a correct (m, m) and (m, m′) matrix, and its scalar path agrees with its matrix path. It has **not** driven a clustering method through `metric="precomputed"`, because no method declaring `supports_precomputed` exists yet. **You are the first, so correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Pairing table: [CONTRIBUTING §2.5](../CONTRIBUTING.md#25-adding-a-measure).

**File:** `xxcluster/measures/dissimilarity/<name>.py`

A dissimilarity is d(x, y), i.e. how far apart two observations are. Gower for mixed types, DTW for series, a learned Mahalanobis.

---

## A dissimilarity *is* a `BaseComponent`

Unlike a validity index, `BaseDissimilarity` derives from `BaseComponent`, and that is deliberate: some measures are **fitted**. A Mahalanobis distance needs a covariance; a scaled measure needs feature ranges.

Treating those as estimators keeps the fitting inside the contract, where it will be **refitted per fold rather than leaking information across a resampling boundary**. That is the whole reason for the choice: a covariance estimated once on the full dataset and reused inside a stability analysis has seen the held-out rows.

A measure with nothing to estimate (most of them) inherits a working `fit` that records the input dimensions and does nothing else. `_fit` is already a no-op on the base; leave it alone.

---

## Step 1: Declare the properties

```python
class BaseDissimilarity(BaseComponent, ABC):
    is_metric: bool = False
    is_symmetric: bool = True
    accepts_missing: bool = False
    accepts_categorical: bool = False
    bounded: tuple[float, float] | None = None
```

| Attribute | Meaning | Document paragraph |
|---|---|---|
| `is_metric` | Satisfies all three properties of Def. 1 | 3. Properties |
| `is_symmetric` | d(x, y) = d(y, x) | 3. Properties |
| `accepts_missing` | Defined on incomplete input | 4. Applicability |
| `accepts_categorical` | Defined on non-numeric input | 4. Applicability |
| `bounded` | Range, where it has one | 3. Properties |

### `is_metric` does real work

A method whose correctness depends on the triangle inequality (Ward's criterion, any distance-pruning acceleration) **checks this before accepting your measure**. Def. 2 permits a non-metric dissimilarity, so declaring it accurately is what keeps that permission safe.

Default is `False`. Leave it there unless you can show all three properties hold. DTW is the classic case: it is symmetric and non-negative but violates the triangle inequality, so `is_metric = False` and Ward will refuse it, correctly.

### `accepts_missing` / `accepts_categorical` are the point of this group

These decide whether a measure can serve mixed data **without the encoding step that would otherwise impose an arbitrary geometry on the categories**. One-hot encoding makes every pair of categories equidistant; where that is wrong, a mixed-type dissimilarity is the fix rather than the encoding. Gower exists for exactly this.

Declaring `accepts_missing = True` also means imputation can be skipped, and imputation invents observations that then get clustered as if measured.

### `is_symmetric = False` is allowed

Def. 2 permits it, and `PrecomputedMixin._precomputed_symmetric` exists so a method can relax the check. But a method that assumes symmetry and receives an asymmetric matrix produces a plausible-looking wrong answer, so this must be declared, never assumed.

---

## Step 2: Implement both `__call__` and `pairwise`

Both are abstract. They are separate because **the matrix is what methods actually consume**, and computing it in one vectorised pass rather than m² scalar calls is the difference between usable and not.

```python
@register("gower")
class Gower(BaseDissimilarity):
    """<one paragraph: the definition, citing ref_<n>>

    Defined on mixed numeric and categorical features without encoding,
    which is why Sect. 3.3's one-hot step can be skipped where this is
    used. Not a metric: <state why>.
    """

    is_metric = False
    is_symmetric = True
    accepts_missing = True
    accepts_categorical = True
    bounded = (0.0, 1.0)

    def __init__(self, *, weights=None) -> None:
        self.weights = weights

    def __call__(self, x, y) -> float:
        """Dissimilarity between two single observations."""
        return float(self.pairwise(np.atleast_2d(x), np.atleast_2d(y))[0, 0])

    def pairwise(self, X, Y=None):
        """All pairwise dissimilarities, vectorised."""
        X = np.asarray(X)
        Y = X if Y is None else np.asarray(Y)
        ...                      # one vectorised pass, not a double loop
        return D
```

**Define `__call__` in terms of `pairwise`, not the reverse.** One implementation, and the scalar path cannot drift from the matrix path.

**`pairwise(X)` must return (m, m); `pairwise(X, Y)` must return (m, m′).** The first is what a clustering method consumes via `metric="precomputed"`; the second is what `predict` needs to assign new observations against fitted centres.

**A vectorised implementation is a requirement, not an optimisation.** [CONTRIBUTING §2.5](../CONTRIBUTING.md#25-adding-a-measure) names it: *"`pairwise`: vectorised, not m² scalar calls"*. A measure invoked m² times from the interpreter is unusable at any realistic size, and it is also why `PrecomputedMixin` is the practical route into an adapted third-party method: the matrix is computed once and handed over.

### `to_similarity`, if the graph family will use your measure

```python
def to_similarity(self, D, **kwargs):
    """Convert dissimilarities to affinities."""
    raise NotImplementedError      # the base's default
```

The graph-theoretic family needs affinities, not distances. The conversion is a **modelling choice** (a kernel, with its own parameter), so it is explicit rather than implied. Implement it only if you can justify the kernel, and put the justification in the write-up.

---

## Step 3: Verify

```bash
python -c "
import numpy as np
from xxcluster.measures.dissimilarity.<name> import <Class>

X = np.random.default_rng(0).random((6, 4))
d = <Class>().fit(X)

D = d.pairwise(X)
print('shape        ', D.shape)
print('zero diagonal', np.allclose(np.diag(D), 0))
print('non-negative ', (D >= 0).all())
print('symmetric    ', np.allclose(D, D.T), '| declared', d.is_symmetric)
print('scalar==matrix', np.isclose(d(X[0], X[1]), D[0, 1]))
print('rectangular  ', d.pairwise(X, X[:2]).shape)

if d.is_metric:
    i, j, k = 0, 1, 2
    print('triangle     ', D[i, k] <= D[i, j] + D[j, k])
if d.bounded:
    lo, hi = d.bounded
    print('in range     ', (D >= lo).all() and (D <= hi).all())
"
```

Check every property you declared, and only those. **A zero diagonal and non-negativity are required of every dissimilarity**: `check_dissimilarity_matrix` in `core/validation.py` enforces them the moment your matrix reaches a method via `metric="precomputed"`, and a non-zero diagonal is precisely the failure that produces a plausible-looking partition rather than an error.

Then drive a real method with it:

```bash
python -c "
from xxcluster.measures.dissimilarity.<name> import <Class>
from xxcluster.cluster.<...> import <Method>       # one with supports_precomputed
import numpy as np
X = np.random.default_rng(0).random((30, 4))
D = <Class>().fit(X).pairwise(X)
m = <Method>(metric='precomputed').fit(D)
print(m.labels_)
"
```

If that method declares `supports_precomputed=False`, it will validate `D` as a feature matrix instead, which is why the declaration exists.

---

## Step 4: Write-up and notebook

`template/measure_template.tex` into `documentation/sections/clustering_methods/measures/<nn>-<name>.tex`. Labels `sec:measure:<name>:*`.

Paragraph 5 (*Computation and complexity*) must state that `pairwise` is vectorised and give the cost; for a series measure like DTW that cost is the main practical constraint on the whole analysis, and Sect. 8 needs it.

Then [notebook.md](notebook.md). A dissimilarity notebook's evidence is the matrix's declared properties plus a clustering result driven through `metric="precomputed"`; show both.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `check_dissimilarity_matrix` rejects your matrix | non-zero diagonal, negative entries, or asymmetry you did not declare |
| Ward silently accepts a non-metric measure | `is_metric` left at a copied `True`; it defaults to `False` for a reason |
| The analysis is unusably slow | `pairwise` implemented as a double loop over `__call__` |
| `predict` fails on new data | `pairwise(X, Y)` not implemented for the rectangular case |
| A similarity matrix passed where a dissimilarity was expected | use `to_similarity` explicitly; never let a caller guess |
| Categorical data still one-hot encoded upstream | `accepts_categorical` declared but the pipeline was not told to skip the encoder |
