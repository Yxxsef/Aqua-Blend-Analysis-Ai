# Contributing to `cluster_analysis/`

A contribution here is **three things that land together**: a section in the
document, the code it describes, and the notebook that evidences it. One
without the others is incomplete — a section with no code cannot be
reproduced, code with no section cannot be reviewed, and neither can be
believed without the run that produced the numbers.

```
cluster_analysis/
├── documentation/   the document: main.tex + sections/        → Part 1
├── template/        section templates, .tex and .docx         → Part 1
├── xxcluster/       the package                               → Part 2
├── notebooks/       test bed and evidence                     → Part 3
└── requirements.txt
```

| Part | Covers |
|---|---|
| [Part 1](#part-1--the-document) | Writing a section, and the templates that shape it |
| [Part 2](#part-2--the-code) | Adding to `xxcluster/`, tied to the section it documents |
| [Part 3](#part-3--the-notebooks) | Testing what you built and evidencing the benchmark |

Branch naming, commits and pull requests follow [`AI/README.md`](../README.md):
one branch per task, `task-<number>-<short-description>`.

---

# Part 1 — The document

## 1.1 The templates

`template/` holds one template per **kind** of section. Different kinds report
different things, so they are not interchangeable.

| Template | For | Document section | Code counterpart |
|---|---|---|---|
| `method_template` | A clustering method | Sect. 7.2–7.4 | `xxcluster/cluster/…` |
| `dimreduction_template` | A dimensionality reduction technique | Sect. 6.3–6.4 | `xxcluster/dim_red/…` |
| `measure_template` | A dissimilarity measure or validity index | Sect. 7.1 | `xxcluster/measures/…` |

Each exists as `.tex` and `.docx`. Write in whichever you prefer; both feed
`documentation/main.pdf`.

Why the templates differ, concretely: a clustering method reports
hyperparameters and a partition; a reduction technique instead has to answer
whether its mapping extends to unseen points and whether it can be inverted,
and must show its effect on the clustering that follows it; a measure has to
declare its metric properties, or its range and direction. Forcing all three
into one shape would lose exactly the parts that matter.

**The parts within a template are ordered and fixed.** The comparison section
(Sect. 8) aggregates across contributions part by part. A merged, renamed or
reordered part cannot be compared with the others.

## 1.2 Two formats, one source of truth

**The `.tex` file is authoritative.** The `.docx` is generated from it:

```bash
cd template
python build_docx.py              # rebuild all generated templates
python build_docx.py measure      # rebuild one
```

`build_docx.py` copies the styling from `method_template.docx` — which is
hand-made and never overwritten — and replaces only the body, so every
template looks identical in Word.

If you change a `.tex` template, change the matching spec in `build_docx.py`
and commit both files. Keeping the two in step by hand does not survive a
sprint.

Word contributors: **leave the heading levels alone.** The name is Heading 3
and the parts are Heading 4; that is how the file assembles into the document
at the right depth.

## 1.3 Using a template

1. Copy it — never edit in place.
   ```bash
   cp template/dimreduction_template.tex \
      documentation/sections/dimensionality/nonlinear/01-umap.tex
   ```
2. Replace `<NAME>`, and replace the label suffix `template` with the short
   name throughout (`sec:dr:template:overview` → `sec:dr:umap:overview`).
3. Fill every `\placeholder{}` and delete it. A placeholder left in a draft
   renders as guidance text in the PDF.
4. Add one `\input` line under the matching subsection in the section's main
   file — `cluster_main.tex`, `dim_main.tex`.
5. Build and check it: `latexmk -pdf main.tex`.

Do not restate shared material. The dataset (Sect. 3), the preprocessing
pipeline (Sect. 3.3) and the evaluation protocol (Sect. 4) are defined once;
refer to them. Use the symbols in the notation table and introduce no private
notation.

## 1.4 Adding a new kind of template

When a new *kind* of section appears — a task write-up, an EDA finding — add a
template rather than bending an existing one:

1. Write `template/<kind>_template.tex`, following the header-comment
   convention of the existing ones: what it is for, where a copy goes, which
   parts are fixed, and which code file must agree with it.
2. Add a `spec_<kind>()` function and a `SPECS` entry in `build_docx.py`, then
   run it. The block helpers (`h4`, `prompt`, `table`, `checklist`) already
   exist; a spec is a list of parts.
3. Add a row to the table in [1.1](#11-the-templates) and to the mapping table
   in [2.2](#22-where-your-contribution-goes).
4. Create the target directory under `documentation/sections/`.

## 1.5 Changing or removing a template

Labels are referenced from elsewhere in the document, so before deleting or
renaming anything:

```bash
grep -rn "sec:dr:umap" documentation/     # find every reference first
```

Removing a template means deleting both files, its `SPECS` entry, and its rows
in the tables above. Removing a *section* means also deleting its `\input`
line — and leaving the section in place if its results are still cited
elsewhere.

> **Note.** `template/method_template.tex` and
> `documentation/sections/clustering_methods/00-template.tex` are currently
> identical copies. Two copies of one template drift. Treat `template/` as
> canonical; the duplicate under `sections/` should be removed once the team
> agrees.

---

# Part 2 — The code

## 2.1 The pairing rule

**Every code contribution has a documentation counterpart, and specific fields
in the two must agree.** This is not a style preference: the qualitative
comparison table of Sect. 8.2 is *generated* from the `Capabilities`
declarations in the code. A declaration that disagrees with its write-up puts a
false row in the document.

So the order of work is: read the template for your kind, write the code with
that template's parts in view, and fill both together.

Read [`xxcluster/ARCHITECTURE.md`](xxcluster/ARCHITECTURE.md) first — it
explains the contract you are implementing.

## 2.2 Where your contribution goes

| You are adding | Code goes in | Subclass | Document section | Template | Notebook |
|---|---|---|---|---|---|
| A clustering method | `xxcluster/cluster/<family>/<subfamily>/<name>.py` | that subfamily's base | Sect. 7.2–7.4 | `method_template` | required |
| A dim. reduction technique | `xxcluster/dim_red/<linear\|nonlinear>/<name>.py` | `BaseLinearReducer` / `BaseManifoldReducer` | Sect. 6.3–6.4 | `dimreduction_template` | required |
| A dissimilarity measure | `xxcluster/measures/dissimilarity/<name>.py` | `BaseDissimilarity` | Sect. 7.1 | `measure_template` | required |
| A validity index | `xxcluster/measures/validation/{internal,external,relative}.py` | the matching base | Sect. 7.1 | `measure_template` | required |
| A preprocessing step | `xxcluster/pipeline/preprocess.py` | `BasePreprocessor` | Sect. 3.3 | — (add to that section) | recommended |
| A figure type | `xxcluster/viz/<module>.py` | — (plain function) | — | — | recommended |
| A whole task | `xxcluster/tasks/<task>/` | `BaseTask` | new section | new kind, see [1.4](#14-adding-a-new-kind-of-template) | required |

## 2.3 Adding a clustering method

1. **Find the subfamily** under `xxcluster/cluster/`. If its package does not
   exist, create it with an `__init__.py` and a `base.py`, modelled on an
   existing one. Its name should already be in `core.types.SubFamily`.
2. **Write one module**, `<name>.py`, subclassing that subfamily's base.
3. **Mix in only the capabilities it has** — `InductiveMixin` only if it can
   label unseen observations, `NoiseAwareMixin` only if it can decline to
   assign one. The mixin and the declaration must agree.
4. **Prefer adapting** a mature implementation: subclass `AdaptedClusterer` and
   declare `_backend_import`, `_param_map`, `_attr_map`. Implement `_fit`
   natively where no good implementation exists, or where following the
   formulation is the point.
5. **Declare `_capabilities`**, filling it from your write-up (see 2.3.1).
6. **Register it**: `@register("method_name")`. Names are permanent — they
   appear in stored artefacts and in the document's tables.
7. **Write the section** from `method_template`, and the notebook from
   `notebooks/00-template.ipynb`.

Nothing outside your module changes. Selection, evaluation and reporting find
the method through the registry.

### 2.3.1 What must agree

| Document paragraph | Code |
|---|---|
| 1. Overview | Module and class docstring; `Capabilities.family`, `.subfamily` |
| 2. Assumptions and applicability | `requires_n_clusters`, `handles_noise`, `handles_missing`, `handles_categorical`, `scale_invariant`, `deterministic`, `assignment` |
| 3. Formulation | `_fit`, and `criterion` if the method optimises an explicit objective; symbols match the notation table |
| 4. Hyperparameters and tuning | `__init__` parameters — every hyperparameter in the table is a parameter, and every parameter is in the table |
| 5. Complexity | `time_complexity`, `space_complexity`, `scales_to` |
| 6. Application to AquaBlend data | `Capabilities.backend` (native or which library), plus any deviation from the shared pipeline |
| 7. Results | Exported by the notebook — never retyped |
| 8. Limitations | The notebook's caveats |
| — | `doc_label` = the section's `\label`; `references` = the `literature.bib` keys cited |

`doc_label` and `references` are what make the link navigable in both
directions: from a table row back to the prose, and from the prose to the code
that produced it.

## 2.4 Adding a dimensionality reduction technique

Same shape as 2.3, with one part carrying most of the weight.

**Declare `is_inductive` honestly, and make the write-up say the same thing.**
A linear projection applies to unseen points; most manifold learners embed only
the sample they were fitted on. A transductive technique declared inductive
will silently corrupt any pipeline that later calls `predict` — and the
*Out-of-sample and inverse mapping* paragraph is where a reviewer checks it.

| Document paragraph | Code |
|---|---|
| 4. Out-of-sample and inverse mapping | `Capabilities.is_inductive`; whether `transform` accepts new data; whether `inverse_transform` is implemented or refuses |
| 6. Choosing the number of components | `n_components`; evidence from `dim_red/intrinsic_dim.py` |
| 9. Results — structure preservation | `explained_variance_ratio_`, `stress_`, `trustworthiness()` |
| 9. Results — downstream effect | A `ComparisonRun` over the same clustering method, with and without the reduction |

## 2.5 Adding a measure

**A dissimilarity** (`BaseDissimilarity`) — the *Properties* paragraph and the
class attributes are the same statement:

| Paragraph | Code |
|---|---|
| 3. Properties | `is_metric`, `is_symmetric`, `bounded` |
| 4. Applicability | `accepts_missing`, `accepts_categorical` |
| 5. Computation and complexity | `pairwise` — vectorised, not `m²` scalar calls |

`is_metric` does real work: a method whose correctness depends on the triangle
inequality — Ward's criterion, any distance-pruning acceleration — checks it
before accepting your measure. Def. 2 permits a non-metric dissimilarity, so
declaring it accurately is what keeps that permission safe.

**A validity index** (`BaseValidityIndex` and its internal/external/relative
subclasses):

| Paragraph | Code |
|---|---|
| 3. Properties | `higher_is_better` (**required, no default**), `range_`, `chance_corrected` |
| 4. Applicability | `requires_labels_true`, `requires_X`, `handles_noise` |
| 7. Behaviour | `assumes_shape` for an internal index |

An index whose direction is assumed is one that will eventually be compared the
wrong way round — which inverts a conclusion rather than breaking a test.

## 2.6 Adding a task (extending sideways)

Time-series clustering, anomaly detection, scenario generation, demand
forecasting: a subpackage under `xxcluster/tasks/`, subclassing `BaseTask`.

**A task composes components; it does not implement algorithms.** Anything
reusable goes in the subpackage for its kind — a series dissimilarity in
`measures/dissimilarity/`, a detector on `BaseOutlierDetector`, a generator on
`BaseGenerator`. A component defined inside a task is invisible to the registry
and to the comparison.

A task needs its own document section, and therefore a new template kind
([1.4](#14-adding-a-new-kind-of-template)). Scenario generation additionally
feeds the MILP team — agree the output format with them before building it.

## 2.7 The contract

Four rules, all mechanically checkable. Full detail in
[`ARCHITECTURE.md §3`](xxcluster/ARCHITECTURE.md).

1. Parameters in `__init__` only, stored unmodified, never validated there.
2. Fitted state set by `fit`, named with a trailing underscore.
3. Override `_fit`, never `fit`.
4. Declare `_capabilities`.

Conventions: noise is `-1` everywhere; `n_clusters` is a request and
`n_clusters_` a result; `from __future__ import annotations` at the top of
every module; docstrings cite the document by section and literature by
`literature.bib` key.

**Notation.** Follow the document's table: `m` observations, `n` features,
`|C|` clusters, `d(·,·)` for the dissimilarity. Docstring array shapes use it —
a feature matrix is `(m, n)`, a dissimilarity matrix `(m, m)`, labels `(m,)`,
an embedding `(m, n_components)`. scikit-learn spells the same axes
`n_samples` and `n_features_in_`; those are API names, not notation, and stay
as they are. If your method needs a symbol the table does not declare — the
fuzzifier exponent is the current example — declare it in
`sections/notation.tex` rather than introducing it privately, and check it does
not collide with `m`, `n` or `d`.

Once your `fit` works, check it:

```python
from sklearn.utils.estimator_checks import check_estimator
check_estimator(YourMethod(n_clusters=3))
```

Some checks will not apply — precomputed metrics, transductive transforms,
parameters with no sensible default. Record the exclusions rather than
loosening the contract, and treat every other failure as a real bug.

## 2.8 When things change

| Change | What to touch |
|---|---|
| New subfamily | Package with `__init__.py` + `base.py`; add the member to `SubFamily` |
| Rename a registered name | **Don't** — it appears in stored artefacts and published tables. If unavoidable, re-run the notebooks that produced those artefacts |
| Remove a method | The module, its `\input` line, its notebook. Keep the section if its results are still cited |
| New optional backend | An entry in the commented block of `requirements.txt`; import it at fit time, never at import time |
| New component kind | A base class in `core/base.py` and a `ComponentKind` member — the contract is designed to be extended here, not worked around |

---

# Part 3 — The notebooks

## 3.1 What a notebook is for

Two jobs, both required:

1. **A test bed** — where you check that what you implemented in `xxcluster/`
   behaves, before it is reported.
2. **Evidence** — the run that produced the numbers and figures in the
   document. A benchmark in the document with no notebook behind it is an
   assertion.

## 3.2 One notebook per contribution

```bash
cp notebooks/00-template.ipynb notebooks/03-hdbscan.ipynb
```

Name it to match the code module and the document subsection it belongs to.
Do not accumulate several methods in one notebook: the reviewer reads one
notebook against one write-up.

## 3.3 The structure

The template's sections mirror the write-up's parts, in the same order, so the
two can be read side by side:

| Notebook section | Purpose |
|---|---|
| 1. Setup | Seed and `Environment.capture()` — reproducibility first |
| 2. Scope | What is tested, and what would count as a negative result |
| 3. Data | Loaded through `xxcluster.io`, never a bare `read_csv` |
| 4. Protocol | The shared setup — taken as given, not tuned here |
| 5. Contract check | The component honours the contract before any result is read |
| 6. Selection | How \|C\| was chosen, **and** whether it survives perturbation |
| 7. Results | Every index in the protocol, favourable or not |
| 8. Figures | Saved into `documentation/figures/` |
| 9. Export | Tables written to `documentation/tables/` |
| 10. Findings and caveats | The bridge to the write-up |

Section 2 asks you to name a negative result in advance. That is what stops a
notebook from becoming a search for a favourable configuration.

## 3.4 From notebook to document

Numbers and figures reach the document by **export, never by retyping** — that
is the most likely place for a result to be corrupted.

```python
table.to_latex("../documentation/tables/hdbscan-results.tex", label="tab:hdbscan:results")
plt.savefig("../documentation/figures/hdbscan-selection.png", dpi=200, bbox_inches="tight")
```

Then `\input` the table and `\includegraphics` the figure under the names above.
Re-running the notebook refreshes the document without editing a section file.

Section 10 of the template maps each output to the paragraph it supports. Fill
it in last, and put the caveats in it — inconclusive selections, unstable
partitions, failed runs. Those belong in the *Limitations* paragraph and in
Sect. 4.5. **They are part of the result, not an embarrassment to omit.**

## 3.5 Reproducibility

- One `RANDOM_STATE`, set in Section 1; everything else derives from it.
- `Environment.capture()` records versions and revision at run time. Do not
  maintain a second version list by hand — `requirements.txt` states the
  floor, the artefact states what actually ran.
- Before committing: **Kernel → Restart & Run All.** A notebook that only runs
  in the order you happened to execute cells is not evidence.

## 3.6 What to commit

- **Commit the outputs.** They are the evidence. (`.ipynb_checkpoints/` is
  already ignored.)
- **Never commit data.** Load it through `xxcluster.io`; raw data belongs to
  the Data Engineering team's folder.
- If a notebook grows past a few MB of embedded images, save the figures to
  `documentation/figures/` and reference them instead of inlining.

---

# Before opening a pull request

- [ ] Section written from the right template, all parts present and in order,
      every `\placeholder{}` filled and deleted.
- [ ] `.docx` regenerated if a `.tex` template changed.
- [ ] `documentation/main.pdf` builds, and the new `\input` line is in place.
- [ ] Code subclasses the right base, mixes in only the capabilities it has,
      and is registered under a permanent name.
- [ ] `_capabilities` agrees with the write-up, field by field
      ([2.3.1](#231-what-must-agree)).
- [ ] `doc_label` and `references` set.
- [ ] Notebook runs top to bottom on a restarted kernel.
- [ ] Tables and figures exported, not retyped.
- [ ] Caveats reported, including unfavourable results.
- [ ] Branch named `task-<number>-<short-description>`; changes confined to
      `AI/` ([`AI/README.md`](../README.md)).
