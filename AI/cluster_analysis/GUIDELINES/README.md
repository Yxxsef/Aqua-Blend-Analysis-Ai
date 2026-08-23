# GUIDELINES: how to build a contribution

**[CONTRIBUTING.md](../CONTRIBUTING.md) is the rule. These are the procedures.**

CONTRIBUTING says *where* your code goes, *what* must agree with the write-up, and *what* the pull request must contain. It does not say how to build the thing. That is here: one guide per kind of addition, each with the base class to pick, the declarations to fill, a skeleton, and a command that proves it works.

Nothing here restates CONTRIBUTING's tables. Where a guide needs a rule, it links to the section that owns it. If the two ever disagree, CONTRIBUTING wins and the guide is wrong; say so in the pull request.

---

## Which guide do I need?

| You are adding | Guide | Document template |
|---|---|---|
| A clustering method (K-Means, DBSCAN, Ward) | [clustering-method.md](clustering-method.md) | `method_template` |
| A dimensionality reduction technique (PCA, UMAP) | [dim-reduction.md](dim-reduction.md) | `dimreduction_template` |
| An internal index (Silhouette, Davies–Bouldin) | [validity-index-internal.md](validity-index-internal.md) | `measure_template` |
| An external index (ARI, NMI) | [validity-index-external.md](validity-index-external.md) | `measure_template` |
| A relative criterion (elbow, gap statistic) | [validity-index-relative.md](validity-index-relative.md) | `measure_template` |
| A dissimilarity measure (Gower, DTW) | [dissimilarity-measure.md](dissimilarity-measure.md) | `measure_template` |
| A preprocessing step (a scaler, an encoder) | [preprocessing-step.md](preprocessing-step.md) | n/a (Sect. 3.3) |
| A selector (sweeps `\|C\|` or a density parameter) | [selection-selector.md](selection-selector.md) | n/a (Sect. 4.3) |
| A perturbation (bootstrap, subsample, jitter) | [selection-perturbation.md](selection-perturbation.md) | n/a (Sect. 4.3) |
| A figure type | [visualisation.md](visualisation.md) | n/a |
| A whole task (time-series clustering, forecasting) | [task.md](task.md) | new kind |
| The notebook that evidences any of the above | [notebook.md](notebook.md) | n/a |

**Read [00-the-contract.md](00-the-contract.md) first, whatever you are adding.** It covers the six rules every component obeys: the template method, fitted-attribute declaration, capabilities, registration, mixins and verification. Each guide assumes it and does not repeat it.

**[worked-example.md](worked-example.md)** carries one complete contribution (K-Means and Silhouette) from empty file to exported table. Read it alongside your guide when you want to see what the steps look like actually carried out.

---

## Status banners

Only part of this package has a real implementation to check a procedure against. Every guide states which case it is in, at the top:

| Banner | Means |
|---|---|
| **Verified** | The procedure was executed against code in this repository. The commands ran and produced the output shown. |
| **Derived from the contract** | The base classes, templates and rules are real and were read directly. The skeleton is import-checked but has not been fitted end to end, because nothing of this kind exists yet. |

A derived guide is not a guess; it is read off the base class you will subclass. But you are the first to run it, so **correct the guide as you go** and change its banner in the same pull request. That is expected work, not a favour.

---

## Before you start

Run everything from `cluster_analysis/`, with the project environment:

```bash
./.venv/bin/python -m pytest          # 260 tests, should be green before you begin
```

The guides write `python` for brevity; use `./.venv/bin/python`, or activate the venv first. `xxcluster` requires scikit-learn ≥ 1.6 and will refuse to import below it; see `requirements.txt`.

Three things worth knowing before your first contribution:

1. **Registered names are permanent.** They land in stored artefacts and in the document's tables. `REGISTRY` refuses to rebind one.
2. **Sect. 8.2 of the document is generated from `Capabilities`.** A declaration that disagrees with your write-up puts a false row in the document. This is why CONTRIBUTING §2.1 tells you to fill both together.
3. **Nothing outside your module should change.** Selection, evaluation and reporting find your component through the registry. If you find yourself editing `core/`, stop and say why in the pull request; it may be a real contract gap, and those get fixed in their own commit.
