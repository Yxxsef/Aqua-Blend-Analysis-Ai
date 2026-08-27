# Adding a relative criterion

> **Status: derived from the contract, skeleton executed.** No relative criterion exists yet, and `selection/n_clusters.py` is blocked on this file. The `MaxCriterion` skeleton below was run: it picks the peak, loses NaN candidates, and returns an ordered curve. It has **not** driven a selector, because none is implemented. **You are the first, so correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Pairing table: [CONTRIBUTING §2.5](../CONTRIBUTING.md#25-adding-a-measure).

**File:** `xxcluster/measures/validation/relative.py`; append to it.

---

## This is not an index; it is a selection *rule*

The distinction from the other two groups is the **unit of assessment**:

- An internal or external index **scores one partition**.
- A relative criterion **reads a sequence of scores and selects from it**.

Most relative criteria are built on an internal index evaluated repeatedly, but the rule is separate from the index and worth naming: the same silhouette curve yields different answers under *"take the maximum"* and *"take the largest |C| within one standard error of the maximum"*. Those are two criteria over one curve, and the document must be able to say which produced a number.

Consequently `BaseRelativeCriterion` derives from `ABC` directly, **not** from `BaseValidityIndex`. It has no `score`, no `higher_is_better`, no `handles_noise`. Do not try to inherit from the index base.

---

## Step 1: The three methods

```python
class BaseRelativeCriterion(ABC):
    name: str
    base_index: str | None = None

    @abstractmethod
    def select(self, scores: Mapping[Any, float], **kwargs) -> Any: ...
    def curve(self, scores: Mapping[Any, float]) -> Sequence[float]: ...
    def is_conclusive(self, scores: Mapping[Any, float]) -> bool: ...
```

| Method | Returns | Why it exists |
|---|---|---|
| `select` | the **key** the criterion prefers | Returning the key, not the score, keeps the rule independent of what is being swept, so the same criterion then works over a density parameter |
| `curve` | the sequence it read | Selection is a judgement and a reader is entitled to see the curve behind it. Consumed by `viz.diagnostics.plot_selection_curve` |
| `is_conclusive` | whether the curve supports a selection at all | A flat or monotone curve means the data does not distinguish the candidates |

`select` is the only abstract one. `curve` and `is_conclusive` raise `NotImplementedError` on the base, but **implement both anyway**. `BaseNClustersSelector` promises `curve_` and `conclusive_` as fitted attributes, and it gets them from here.

### `base_index` is required in practice

Name the index whose curve you read. *"The elbow"* is not a result on its own: the curve it was read from is part of the finding, and this attribute is what records it.

```python
base_index = "silhouette"     # or None for a criterion that computes its own
```

### `is_conclusive` is the point of this class

Returning an arbitrary argmax over a flat curve produces a number that later reads as a finding. Saying *"the data does not distinguish 2 through 10 clusters"* is a **valid outcome and a better one**. Sect. 4.5 wants it, and `plot_selection_curve` draws the curve either way precisely so an inconclusive result stays visible.

Give it a real test, not a placeholder:

```python
def is_conclusive(self, scores):
    values = np.asarray(list(scores.values()), dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 3:
        return False
    spread = float(np.nanmax(values) - np.nanmin(values))
    return spread >= self.min_spread      # a declared parameter, not a constant
```

Whatever rule you choose, **state it in the write-up**. A conclusiveness threshold is a modelling decision, and burying it in a magic number hides it.

---

## Step 2: Skeleton

```python
@register("max_criterion")
class MaxCriterion(BaseRelativeCriterion):
    """Take the candidate with the best score, subject to a spread test.

    The simplest rule, and the honest baseline the others are compared
    against. Direction comes from the index rather than being assumed
    here; see `BaseValidityIndex.is_better`.

    Applied per Sect. 4.3.
    """

    name = "max_criterion"
    base_index = "silhouette"

    def __init__(self, *, index=None, min_spread: float = 0.0) -> None:
        self.index = index                # a BaseValidityIndex, for direction
        self.min_spread = min_spread

    def select(self, scores, **kwargs):
        if not scores:
            raise ValueError("no candidates were scored; nothing to select.")
        best = None
        for candidate, value in scores.items():
            if best is None or self._is_better(value, scores[best]):
                best = candidate
        if best is None or not np.isfinite(scores[best]):
            raise ValueError(
                f"no candidate produced a finite {self.base_index} score."
            )
        return best

    def curve(self, scores):
        return [scores[k] for k in scores]

    def is_conclusive(self, scores):
        ...

    def _is_better(self, a, b):
        if self.index is not None:
            return self.index.is_better(a, b)     # direction from the index
        raise ValueError(
            f"{self.name} needs an index to know which direction is better. "
            f"Pass index=Silhouette(), or set it from the protocol."
        )
```

**Never hard-code `>`.** Half the indices in this package are minimised. Direction belongs to the index, and `BaseValidityIndex.is_better` is the single place it is applied; it is also NaN-safe, so a failed candidate loses rather than propagating. A criterion that assumes higher-is-better silently inverts every Davies–Bouldin sweep.

**Preserve insertion order in `curve`.** `plot_selection_curve` plots keys against values in the order it receives them; a dict comprehension over `range(2, 11)` is already ordered, and re-sorting would misalign the figure from the sweep.

---

## Step 3: Verify

```bash
python -c "
import numpy as np
from xxcluster.measures.validation.internal import Silhouette
from xxcluster.measures.validation.relative import <Class>

peaked  = {2: 0.68, 3: 0.55, 4: 0.50, 5: 0.49}
flat    = {2: 0.50, 3: 0.50, 4: 0.50, 5: 0.50}
withnan = {2: 0.68, 3: float('nan'), 4: 0.50}

c = <Class>(index=Silhouette())
print('peak       ', c.select(peaked), '   (expect 2)')
print('conclusive ', c.is_conclusive(peaked), c.is_conclusive(flat))
print('nan loses  ', c.select(withnan), '   (expect 2)')
print('curve      ', list(c.curve(peaked)))
"
```

Then check it against a minimised index, which is where a hard-coded `>` shows up:

```bash
python -c "
from xxcluster.measures.validation.internal import DaviesBouldin   # if it exists
from xxcluster.measures.validation.relative import <Class>
c = <Class>(index=DaviesBouldin())
print(c.select({2: 0.9, 3: 0.4, 4: 1.2}), '  (expect 3, lower is better)')
"
```

Finally, draw it, since the figure is half the deliverable:

```bash
python -c "
import matplotlib; matplotlib.use('Agg')
from xxcluster.viz.diagnostics import plot_selection_curve
curve = {2: 0.68, 3: 0.55, 4: 0.50}
plot_selection_curve(curve, selected=2, criterion='<name>')
print('figure OK')
"
```

---

## What you unblock

`selection/n_clusters.py` cannot be written without a concrete criterion: `BaseNClustersSelector` gets two of its three fitted attributes from `criterion.curve()` and `criterion.is_conclusive()`. Once yours exists, see [selection-selector.md](selection-selector.md).

Until then, notebooks inline the rule by hand (`max(curve, key=curve.get)`), which is exactly the ambiguity this class removes.

---

## Write-up

`template/measure_template.tex` into `documentation/sections/clustering_methods/validity/<nn>-<name>.tex`, labels `sec:measure:<name>:*`. The paragraphs that carry a code counterpart:

| Paragraph | Code |
|---|---|
| 3. Properties | `base_index`, and the direction rule you apply |
| 4. Applicability | what shape of curve the criterion assumes |
| 7. Behaviour | your `is_conclusive` rule, stated as a threshold with units |

---

## Common mistakes

| Symptom | Cause |
|---|---|
| Every Davies–Bouldin sweep selects the worst |C| | hard-coded `>` instead of `index.is_better` |
| `select` returns a candidate on a perfectly flat curve | `is_conclusive` not implemented, or not consulted by the caller |
| Figure's x-axis is out of order | `curve` re-sorted the keys |
| `_fit did not set: conclusive_` in a selector | `is_conclusive` still raising `NotImplementedError` |
| A NaN candidate wins | direction applied with a bare comparison rather than `is_better` |
