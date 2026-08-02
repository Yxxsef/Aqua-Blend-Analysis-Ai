# Adding a figure type

> **Status: verified.** All eleven functions in `viz/` are implemented; the
> conventions below are read off them and the smoke test at the end runs.

**Read [00-the-contract.md](00-the-contract.md) first** — though most of it
does not apply here. A figure function is **a plain function**, not a
component: no base class, no registration, no capabilities.

**File:** `xxcluster/viz/<module>.py`

| Module | Holds |
|---|---|
| `dendrogram.py` | hierarchies — `plot_dendrogram`, `plot_merge_heights` |
| `embedding.py` | reduced spaces — `plot_embedding`, `plot_component_loadings`, `plot_feature_pairs` |
| `diagnostics.py` | selection and per-observation validity — `plot_selection_curve`, `plot_silhouette`, `plot_stability`, `plot_cluster_profiles` |

Add to the module whose subject matches. A new module needs a line in
`viz/__init__.py`'s docstring table.

---

## The two rules

### 1. Take fitted results; never fit anything

> A plotting routine that quietly refits produces a figure of something other
> than the result being discussed.

This is the one rule that is not negotiable. Your function receives a fitted
model, a label vector, or a plain mapping — and reads it. If you find yourself
needing to fit, the caller should have done it and passed the result.

The helpers `_linkage_of(model)` and `_embedding_of(model)` exist for this: they
pull the array off a fitted model, and raise if it is not there.

### 2. The figure must carry what is needed to read it

> A figure in a report is separated from the code that made it.

Which method, which measure, which parameter values. A silhouette plot without
the metric named is not interpretable six months later, and neither is a
selection curve without the criterion.

Two conventions follow:

- **Name the rule in the legend, not the title.** The same curve read by two
  criteria gives two figures that must be distinguishable at a glance —
  `plot_selection_curve(..., criterion="max silhouette")` does this.
- **Show the inconclusive case.** `plot_selection_curve` draws the curve
  whether or not the criterion found it conclusive; hiding it would turn an
  arbitrary argmax into an apparent result.

---

## Signature convention

Every function in `viz/` follows the same shape:

```python
def plot_<thing>(
    <required positional>,
    *,
    <options>,
    ax: Any = None,
    **kwargs: Any,
) -> Any:
    """<one line>

    <why this figure exists, and what it must carry to be readable>
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()
    ...
    return ax
```

Four things this buys you:

- **`import matplotlib.pyplot` inside the function.** Keeps `import xxcluster`
  free of the backend, and matches the rest of `viz/`.
- **`ax=None` and return the `ax`.** Lets a caller compose a multi-panel figure;
  never call `plt.show()` or `plt.savefig()` yourself — that is the notebook's
  job.
- **`**kwargs` forwarded to the matplotlib call.** So a caller can restyle
  without a new parameter.
- **Validate and raise early.** `plot_selection_curve` raises
  `ValueError("curve is empty; nothing was swept.")` rather than drawing an
  empty axes — an empty figure in a document is worse than an error in a
  notebook.

---

## Skeleton

```python
def plot_cluster_sizes(labels: Any, *, ax: Any = None, **kwargs: Any) -> Any:
    """Bar chart of cluster sizes, with noise shown separately.

    Reports how many observations a method declined to assign as its own
    bar rather than dropping it: that count is a property of the result
    (Sect. 4.4), and a figure that hides it overstates the coverage of the
    partition.
    """
    import matplotlib.pyplot as plt

    labels = check_labels(labels)
    if labels.size == 0:
        raise ValueError("labels is empty; nothing to plot.")

    if ax is None:
        _, ax = plt.subplots()

    values, counts = np.unique(labels, return_counts=True)
    colours = ["0.6" if v == NOISE_LABEL else None for v in values]
    ax.bar([str(v) for v in values], counts, color=colours, **kwargs)
    ax.set_xlabel("cluster")
    ax.set_ylabel("observations")
    return ax
```

**Noise gets its own visual treatment**, here and everywhere. `-1` is not
cluster number minus one; colouring it like an ordinary cluster is the same
category error as scoring it like one.

---

## Verify

Figures need an eyeball, but three things are worth asserting:

```bash
python -c "
import matplotlib; matplotlib.use('Agg')
import numpy as np
from xxcluster.viz.<module> import <plot_fn>

labels = np.array([0,0,1,1,2,-1])

ax = <plot_fn>(labels)
print('returns an axes  ', ax is not None)

import matplotlib.pyplot as plt
_, mine = plt.subplots()
print('honours ax=      ', <plot_fn>(labels, ax=mine) is mine)

try:
    <plot_fn>(np.array([]))
    print('empty input      ACCEPTED — should it be?')
except ValueError as e:
    print('empty input      refused:', str(e)[:50])
"
```

Then render it for real and look at it:

```bash
python -c "
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from xxcluster.viz.<module> import <plot_fn>
<plot_fn>(...)
plt.savefig('/tmp/check.png', dpi=200, bbox_inches='tight')
"
```

---

## Getting it into the document

The notebook saves it; the document `\includegraphics` it. Nothing else writes
to `documentation/figures/`.

```python
FIGURES = ROOT / "documentation" / "figures"
ax = plot_<thing>(...)
plt.savefig(FIGURES / "<name>-<what>.png", dpi=200, bbox_inches="tight")
```

`dpi=200, bbox_inches="tight"` throughout, and the filename pattern
`<method>-<what>.png` so the document's reference is guessable from the method
name. Pick the names before you write the figure — the document references the
path verbatim.

A figure must be **reproducible from the artefact and seed recorded with it**.
In practice that means the notebook that draws it also captured
`Environment.capture()` and set `RANDOM_STATE` once — see
[notebook.md](notebook.md).

---

## Common mistakes

| Symptom | Cause |
|---|---|
| The figure shows a different partition than the table | the function refit; it must only read |
| Two selection curves in the document are indistinguishable | criterion not named in the legend |
| An empty axes in the document | no validation; raise instead |
| Noise plotted as an ordinary cluster | `-1` treated as a label rather than a sentinel |
| A caller cannot compose panels | `ax=` not honoured, or `plt.show()` called inside |
| The figure cannot be regenerated | drawn in a cell with no seed and no captured environment |
