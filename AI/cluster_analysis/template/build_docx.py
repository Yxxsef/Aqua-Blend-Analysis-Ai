"""
Build the .docx templates from the specs below.

    python build_docx.py            # rebuild every generated template
    python build_docx.py measure    # rebuild one

Each template exists in two formats. Contributors who write in LaTeX use
the .tex file; contributors who write in Word use the .docx. Both feed
documentation/main.pdf, so the two must say the same thing -- and the
.tex file is authoritative wherever they disagree.

Keeping them in step by hand does not survive a sprint, so the .docx
files are generated. Edit the spec here, run the script, commit both.

Styling is not defined here: the script copies every part of
style_donor.docx except the document body, so generated templates
inherit that file's styles, numbering and page setup and look identical
in Word. style_donor.docx is the hand-made original of
method_template.docx, kept only for its styles; it is never overwritten
and is not a template anyone writes in. Every template, method included,
is generated.

Adding a template: write the .tex file, add a spec function below, add
it to SPECS, and run the script. Removing one: delete both files and its
entry. No other file needs to change.

Uses only the standard library.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
DONOR = HERE / "style_donor.docx"

# --- Palette, matching method_template.docx -------------------------------
NAVY = "1F3A5F"
GREY = "595959"
RULE = "BFC9D4"
TINT = "F2F5F8"

FOOTER = (
    "This Word template mirrors the LaTeX template of the same name. "
    "If the two ever disagree, the LaTeX template in the repository is "
    "authoritative."
)

# --- Shared links ---------------------------------------------------------
# Every contributor declares their sources in this sheet and is given a
# ref_<n> key for each; the document lead applies those keys to
# documentation/literature.bib.
CITATION_SHEET = (
    "https://deakin365-my.sharepoint.com/:x:/g/personal/s224236373_deakin_edu_au/"
    "IQDSW3PBbHhZSq6vzGGQqi3WAbgJ1id1-t02k5B6fduX5Ys?e=nShY5e"
)
TURNITIN_POLICY = (
    "https://d2l.deakin.edu.au/d2l/le/content/93067/viewContent/5882569/View"
)

REFERENCES_PROMPT = (
    "Every source this write-up draws on, listed by its ref_<n> key from the "
    "citation key mapping sheet — including anything you read and did not cite, "
    "since a reviewer needs to see what the write-up rests on and not only what it "
    "quotes. Declare the source in the sheet first; the key comes from there. Fill "
    "in the table below."
)
REFERENCES_TABLE_HEADERS = ["Ref key", "Source (author, year, title)", "Where used"]
REFERENCES_TABLE_WIDTHS = [1200, 4800, 3000]


# --- Block helpers: each returns one paragraph or table as XML -------------


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text: str, *, bold=False, italic=False, color=None, size=None) -> str:
    props = ""
    if bold:
        props += "<w:b/><w:bCs/>"
    if italic:
        props += "<w:i/><w:iCs/>"
    if color:
        props += f'<w:color w:val="{color}"/>'
    if size:
        props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def _para(text: str, *, ppr: str = "", **run_kwargs) -> str:
    ppr_xml = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f"<w:p>{ppr_xml}{_run(text, **run_kwargs)}</w:p>"


def title(text: str) -> str:
    return _para(text, ppr='<w:spacing w:after="60"/>', bold=True, color=NAVY, size="34")


def subtitle(text: str) -> str:
    ppr = (
        f'<w:pBdr><w:bottom w:val="single" w:color="{RULE}" w:sz="6" w:space="6"/></w:pBdr>'
        '<w:spacing w:after="240"/>'
    )
    return _para(text, ppr=ppr, italic=True, color=GREY, size="21")


def callout(text: str) -> str:
    """Tinted band used for the 'How to use' headings."""
    ppr = (
        f'<w:shd w:fill="{TINT}" w:color="auto" w:val="clear"/>'
        '<w:spacing w:after="140"/><w:ind w:left="200" w:right="200"/>'
    )
    return _para(text, ppr=ppr, bold=True, color=NAVY, size="24")


def body(text: str) -> str:
    return _para(text, ppr='<w:spacing w:after="120"/>', size="21")


def meta(text: str) -> str:
    ppr = (
        f'<w:pBdr><w:bottom w:val="single" w:color="{RULE}" w:sz="6" w:space="6"/></w:pBdr>'
        '<w:spacing w:after="60"/>'
    )
    return _para(text, ppr=ppr, italic=True, color=GREY, size="20")


def h3(text: str) -> str:
    return _para(text, ppr='<w:pStyle w:val="Heading3"/>')


def h4(text: str) -> str:
    return _para(text, ppr='<w:pStyle w:val="Heading4"/>')


def prompt(text: str) -> str:
    """The bracketed italic instruction a contributor deletes."""
    ppr = '<w:spacing w:after="200" w:before="60"/>'
    return _para(f"[{text}]", ppr=ppr, italic=True, color=GREY, size="21")


def bullet(text: str) -> str:
    ppr = '<w:pStyle w:val="ListParagraph"/><w:spacing w:after="40"/><w:ind w:left="360"/>'
    return _para(text, ppr=ppr, size="21")


def footer(text: str = FOOTER) -> str:
    ppr = (
        f'<w:pBdr><w:top w:val="single" w:color="{RULE}" w:sz="6" w:space="8"/></w:pBdr>'
        '<w:spacing w:before="300"/>'
    )
    return _para(text, ppr=ppr, italic=True, color=GREY, size="19")


def table(headers: list[str], widths: list[int], n_blank_rows: int = 3) -> str:
    borders = "".join(
        f'<w:{e} w:val="single" w:color="auto" w:sz="4"/>'
        for e in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    margins = (
        '<w:tcMar><w:top w:type="dxa" w:w="80"/><w:left w:type="dxa" w:w="100"/>'
        '<w:bottom w:type="dxa" w:w="80"/><w:right w:type="dxa" w:w="100"/></w:tcMar>'
    )

    def cell(text: str, width: int, *, header: bool) -> str:
        shd = f'<w:shd w:fill="{NAVY}" w:color="auto" w:val="clear"/>' if header else ""
        run = (
            _run(text, bold=True, color="FFFFFF", size="20")
            if header
            else _run(text, size="20")
        )
        return (
            f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{width}"/>{shd}{margins}</w:tcPr>'
            f"<w:p>{run}</w:p></w:tc>"
        )

    head = "<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(
        cell(h, w, header=True) for h, w in zip(headers, widths)
    ) + "</w:tr>"
    blank = "".join(
        "<w:tr>" + "".join(cell("", w, header=False) for w in widths) + "</w:tr>"
        for _ in range(n_blank_rows)
    )
    return (
        f'<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="{sum(widths)}"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{head}{blank}</w:tbl>"
        '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr></w:p>'
    )


def checklist(items: list[str]) -> list[str]:
    return [h3("Before submitting")] + [bullet(i) for i in items]


# --- Shared front matter ---------------------------------------------------


def front(kind: str, tex_name: str, target: str, order_note: str) -> list[str]:
    return [
        title(f"{kind} Write-Up — Template"),
        subtitle(f"AquaBlend · Analysis & AI · Word equivalent of template/{tex_name}"),
        callout("How to use this template"),
        body(
            f"Copy this file — do not edit it in place. Save your copy as {target}, "
            "and hand it to whoever assembles the document."
        ),
        body(order_note),
        body(
            "Heading levels are deliberate. The name is Heading 3 and the parts are "
            "Heading 4, so the file assembles into the document at the right depth. "
            "Do not change them."
        ),
        callout("Cross-references and shared material"),
        body(
            "Where the LaTeX template points at a label, refer to the section by name "
            "instead and let the assembler insert the reference. Do not restate shared "
            "material — the dataset, the preprocessing pipeline, the evaluation "
            "protocol — refer to the section that defines it."
        ),
        body(
            "Use the symbols declared in the shared notation table. Do not introduce "
            "private notation."
        ),
        callout("References — declare, then cite"),
        body(
            "Every source you use is declared in the shared citation key mapping "
            "sheet, and nowhere else. Everyone's references go in the same sheet: "
            + CITATION_SHEET
        ),
        body(
            "Each entry there carries a key of the form ref_<n>. Refer to a source by "
            "that key in your text — \"the objective of ref_12\" — and list it in the "
            "References part at the end of this template. The document lead turns "
            "those keys into the document's citations; do not edit literature.bib "
            "yourself, and do not invent your own key."
        ),
        body(
            "Cite in the part where the claim is made, not in a lump at the end. "
            "Every formulation, every published result and every parameter value "
            "taken from the literature carries its own reference."
        ),
        callout("Academic integrity"),
        body(
            "An uncited claim, figure, equation, table or code fragment is "
            "plagiarism, whether it came from a paper, a library's documentation, a "
            "teammate, or a generative AI tool. Quote and cite it, or write it "
            "yourself. Declare AI assistance as Deakin policy requires."
        ),
        body(
            "Before opening the pull request, run your section through Turnitin. Do "
            "not commit the report — the repository is not where it belongs. Paste "
            "the similarity summary into the pull request as an image, or send it to "
            "the document lead privately; the lead may also run the check later. "
            "Turnitin is available to Deakin students. Policy and procedure: "
            + TURNITIN_POLICY
        ),
    ]


# --- Specs -----------------------------------------------------------------


def spec_method() -> list[str]:
    parts = [
        ("1. Overview", "What the algorithm does, in one paragraph, and which family it belongs to."),
        ("2. Assumptions and applicability", "What the algorithm assumes about cluster shape, density, scale and noise, and the conditions under which it is a sensible choice for our data. A method whose assumptions the data violates can still be reported — say so here rather than in the limitations."),
        ("3. Formulation", "The objective function and the update rule, using the shared notation. Cite the original source."),
        ("4. Hyperparameters and tuning", "Every hyperparameter, the range searched, and the value selected — each with the reason. Fill in the table below."),
        ("5. Complexity", "Time and space complexity, and what that means at AquaBlend data volumes. Note any step quadratic in the number of observations, since that decides whether the method runs on the full dataset or only on a sample."),
        ("6. Application to AquaBlend data", "Implementation: library and version, random seeds, and how the run is reproduced. Then any deviation from the shared preprocessing pipeline, and why it was necessary."),
        ("7. Results", "The validity measures of the shared protocol, the cluster profiles, and the figures that support them. Report every index in the protocol, favourable or not. Fill in the table below."),
        ("8. Limitations", "Where this method failed on our data, or would be expected to. Distinguish what was observed from what is known from the literature."),
        ("9. Summary", "Two or three sentences: the verdict on this method, phrased so it can be carried directly into the comparison section."),
        ("10. References", REFERENCES_PROMPT),
    ]
    blocks = front(
        "Clustering Method",
        "method_template.tex",
        "clustering_methods/<family>/NN-<name>",
        "Keep the ten parts in the order given. The comparison section aggregates "
        "across methods part by part, so a merged or renamed part cannot be compared "
        "with the others.",
    )
    blocks += [h3("<METHOD NAME>"), meta("Author: <your name>   ·   Family: <hierarchical | partitional | hybrid>   ·   Draft: v0.1   ·   Date: <date>")]
    for heading, text in parts:
        blocks += [h4(heading), prompt(text)]
        if heading.startswith("4."):
            blocks.append(table(
                ["Hyperparameter", "Range searched", "Value selected", "Reason for the choice"],
                [2200, 2200, 1600, 3000],
            ))
        if heading.startswith("7."):
            blocks.append(table(
                ["Validity measure", "Value", "Reading"],
                [3000, 1600, 4400],
            ))
        if heading.startswith("10."):
            blocks.append(table(REFERENCES_TABLE_HEADERS, REFERENCES_TABLE_WIDTHS, 4))
    blocks += checklist([
        "All ten parts present, in the given order, none merged or renamed.",
        "Every bracketed italic prompt deleted.",
        "<METHOD NAME> and the author/family/date line filled in.",
        "Assumptions stated, and matching the code's Capabilities declaration.",
        "How the number of clusters was chosen stated, and whether it survives perturbation.",
        "Every index in the shared protocol reported, including the unfavourable ones.",
        "Notation matches the shared notation table; no private symbols introduced.",
        "Original source of the method cited, in the part where the claim is made.",
        "Every source declared in the citation key mapping sheet and referred to by its ref_<n> key.",
        "References part filled in, including sources read but not cited.",
        "Figures numbered, captioned, and referred to in the text.",
        "Headings left at Heading 3 / Heading 4 so the file assembles correctly.",
        "AI assistance declared per Deakin policy if used in drafting.",
        "Turnitin run; the report shared with the document lead, not committed.",
    ])
    blocks.append(footer())
    return blocks


def spec_dimreduction() -> list[str]:
    parts = [
        ("1. Overview", "What the technique does, in one paragraph: what it maps from, what it maps to, and what it tries to preserve. State whether it is linear or nonlinear, and for a nonlinear technique, its relation to the manifold hypothesis."),
        ("2. Assumptions and applicability", "What the technique assumes — linearity, local versus global structure, density, scale, noise — and when it is a sensible choice for our data. State explicitly whether it is intended for visualisation, for reducing input to a clustering method, or for both: these are different jobs."),
        ("3. Formulation", "The objective being optimised and the mapping obtained, using the shared notation. Cite the original source."),
        ("4. Out-of-sample and inverse mapping", "Two questions, answered explicitly. Is the technique inductive or transductive — does the learned mapping apply to observations unseen during fitting, or does it embed only the fitted sample? And does an inverse mapping exist, so a component can be read back in terms of the measured features? If not, say where the interpretation will come from instead."),
        ("5. Hyperparameters and tuning", "Every hyperparameter, the range searched, and the value selected — each with the reason. Fill in the table below."),
        ("6. Choosing the number of components", "How the target dimension was chosen and on what evidence: explained variance, an intrinsic dimension estimate, reconstruction error, or a downstream requirement. Choosing two because two is what plots is legitimate for a figure and not for an analysis — if that is the reason, say so."),
        ("7. Complexity", "Time and space complexity, and what that means at AquaBlend data volumes. Note any step quadratic in the number of observations, since that decides whether the technique runs on the full dataset or only on a sample."),
        ("8. Application to AquaBlend data", "Implementation: library and version, random seeds, and how the run is reproduced. Then any deviation from the shared preprocessing pipeline and why it was necessary — scaling in particular, since most of these techniques are not scale-invariant."),
        ("9. Results", "Structure preservation first: how faithfully the embedding represents the input, reported quantitatively — explained variance, trustworthiness, stress, reconstruction error — not by appeal to how a scatter plot looks. Then the effect on downstream clustering: the shared validity measures for the same clustering method fitted with and without this reduction. That is what decides whether the technique earns its place."),
        ("10. Limitations", "Where this technique distorted the data, or would be expected to. Distinguish what was observed from what is known from the literature. For nonlinear techniques, state plainly which properties of the embedding must not be read as properties of the data — typically inter-cluster distances, relative cluster sizes, and apparent density."),
        ("11. Summary", "Two or three sentences: the verdict, and whether the technique is recommended for visualisation, for the clustering pipeline, for both, or for neither."),
        ("12. References", REFERENCES_PROMPT),
    ]
    blocks = front(
        "Dimensionality Reduction Technique",
        "dimreduction_template.tex",
        "dimensionality/<linear|nonlinear>/NN-<name>",
        "Keep the twelve parts in the order given. The comparison section aggregates "
        "across techniques part by part, so a merged or renamed part cannot be "
        "compared with the others.",
    )
    blocks += [h3("<TECHNIQUE NAME>"), meta("Author: <your name>   ·   Type: <linear | nonlinear>   ·   Draft: v0.1   ·   Date: <date>")]
    for heading, text in parts:
        blocks += [h4(heading), prompt(text)]
        if heading.startswith("5."):
            blocks.append(table(
                ["Hyperparameter", "Range searched", "Value selected", "Reason for the choice"],
                [2200, 2200, 1600, 3000],
            ))
        if heading.startswith("9."):
            blocks.append(table(
                ["Quantity", "Without reduction", "With reduction", "Reading"],
                [2400, 2100, 2100, 2400],
            ))
        if heading.startswith("12."):
            blocks.append(table(REFERENCES_TABLE_HEADERS, REFERENCES_TABLE_WIDTHS, 4))
    blocks += checklist([
        "All twelve parts present, in the given order, none merged or renamed.",
        "Every bracketed italic prompt deleted.",
        "<TECHNIQUE NAME> and the author/type/date line filled in.",
        "Inductive or transductive stated explicitly, and matching the code's Capabilities declaration.",
        "Number of components justified by evidence, not by convenience.",
        "Structure preservation reported quantitatively, not by appearance.",
        "Downstream clustering compared with and without the reduction.",
        "Notation matches the shared notation table; no private symbols introduced.",
        "Original source of the technique cited, in the part where the claim is made.",
        "Every source declared in the citation key mapping sheet and referred to by its ref_<n> key.",
        "References part filled in, including sources read but not cited.",
        "Figures numbered, captioned, and referred to in the text.",
        "Headings left at Heading 3 / Heading 4 so the file assembles correctly.",
        "AI assistance declared per Deakin policy if used in drafting.",
        "Turnitin run; the report shared with the document lead, not committed.",
    ])
    blocks.append(footer())
    return blocks


def spec_measure() -> list[str]:
    parts = [
        ("1. Overview", "What the measure quantifies, in one paragraph, and which kind it is: a dissimilarity measure, or a validity index — and if an index, whether internal, external or relative. State why it is included: which methods need it, or which question about a partition it answers."),
        ("2. Definition", "The formal definition, using the shared notation. Cite the original source. Where the measure is defined only for particular data types or cluster representations, say so here."),
        ("3. Properties", "For a dissimilarity: which of the three metric properties it satisfies — identity and positivity, symmetry, the triangle inequality — and which it violates. This is not a formality: a measure violating the triangle inequality is admissible, but cannot be used with a method whose correctness depends on it. For an index: the attainable range, the direction (whether high or low is better), whether it is corrected for chance, and whether it is defined in the presence of noise. Fill in the table below."),
        ("4. Applicability", "Which data types the measure accepts — numeric, categorical, mixed, incomplete — and which families of methods it can serve. For an index, add whether it applies to a soft partition directly or only to a defuzzified one, and how observations labelled as noise are treated. Excluding them scores only the points a method was confident about, which flatters that method; whichever choice is made, state it wherever the index is reported."),
        ("5. Computation and complexity", "How the measure is computed, its time and space complexity, and what that means at AquaBlend data volumes. Note whether it requires the full pairwise matrix, since that is quadratic in the number of observations and often the binding constraint."),
        ("6. Application to AquaBlend data", "Implementation, and where the measure is used: which methods are fitted with it, or which results are reported under it. Any parameter it carries, with the value chosen and the reason."),
        ("7. Behaviour", "What the measure rewards, demonstrated rather than asserted — on our data, on a benchmark with known structure, or on a synthetic example. Essential for an index, because every index encodes a notion of what a cluster is: one built on distances to a centroid rewards compact, isotropic clusters and so does not rank methods of different families neutrally. Where that applies, carry it into the threats to validity."),
        ("8. Limitations", "Where the measure is uninformative, misleading, or undefined — degenerate partitions, unbalanced cluster sizes, high dimension, or the concentration of distances. Distinguish what was observed from what is known from the literature."),
        ("9. Summary", "Two or three sentences: what this measure is good for, what it must not be used for, and whether it belongs to the reported protocol or is supplementary."),
        ("10. References", REFERENCES_PROMPT),
    ]
    blocks = front(
        "Measure",
        "measure_template.tex",
        "clustering_methods/measures/NN-<name>",
        "Keep the ten parts in the order given. Parts 3 and 4 carry separate prompts "
        "for a dissimilarity measure and for a validity index — delete whichever does "
        "not apply.",
    )
    blocks += [h3("<MEASURE NAME>"), meta("Author: <your name>   ·   Kind: <dissimilarity | internal | external | relative>   ·   Draft: v0.1   ·   Date: <date>")]
    for heading, text in parts:
        blocks += [h4(heading), prompt(text)]
        if heading.startswith("3."):
            blocks.append(table(
                ["Property", "Holds?", "Evidence or reason"],
                [3000, 1400, 4600],
            ))
        if heading.startswith("10."):
            blocks.append(table(REFERENCES_TABLE_HEADERS, REFERENCES_TABLE_WIDTHS, 4))
    blocks += checklist([
        "All ten parts present, in the given order, none merged or renamed.",
        "Every bracketed italic prompt deleted, including the prompts for the kind that does not apply.",
        "<MEASURE NAME> and the author/kind/date line filled in.",
        "Metric properties stated for a dissimilarity; range, direction and noise handling stated for an index.",
        "Those statements match the class attributes declared in the code.",
        "Behaviour demonstrated on data, not asserted.",
        "Notation matches the shared notation table; no private symbols introduced.",
        "Original source of the measure cited, in the part where the claim is made.",
        "Every source declared in the citation key mapping sheet and referred to by its ref_<n> key.",
        "References part filled in, including sources read but not cited.",
        "Headings left at Heading 3 / Heading 4 so the file assembles correctly.",
        "AI assistance declared per Deakin policy if used in drafting.",
        "Turnitin run; the report shared with the document lead, not committed.",
    ])
    blocks.append(footer())
    return blocks


#: Generated templates. style_donor.docx is not listed: it is the
#: hand-made original the styling is taken from, and is never overwritten.
SPECS = {
    "method": spec_method,
    "dimreduction": spec_dimreduction,
    "measure": spec_measure,
}


# --- Writing ---------------------------------------------------------------


def build(name: str) -> Path:
    """Write <name>_template.docx, taking every non-body part from the donor."""
    if not DONOR.exists():
        raise SystemExit(f"style donor missing: {DONOR}")

    donor = zipfile.ZipFile(DONOR)
    head = donor.read("word/document.xml").decode("utf8")
    # Reuse the donor's namespace declarations and its <w:sectPr> page setup.
    opening = head[: head.index("<w:body>") + len("<w:body>")]
    sect = head[head.index("<w:sectPr>") : head.index("</w:body>")]

    document = opening + "".join(SPECS[name]()) + sect + "</w:body></w:document>"

    out = HERE / f"{name}_template.docx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in donor.namelist():
            if item.endswith("/"):
                continue
            if item == "word/document.xml":
                z.writestr(item, document.encode("utf8"))
            else:
                z.writestr(item, donor.read(item))
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or list(SPECS)
    unknown = [n for n in names if n not in SPECS]
    if unknown:
        raise SystemExit(f"unknown template(s): {', '.join(unknown)}. Known: {', '.join(SPECS)}")
    for n in names:
        print("wrote", build(n).name)
