# Demand Research and Toy-Model Demand Value

**Task:** Task 4 - Research and select the toy-model demand value
**Owner:** Mansoor Shaik
**Stream:** AI and Analysis
**Toy model scope:** 3 reservoirs (e.g. Silvan, Thomson, Sugarloaf), 1 treatment facility, 1 demand zone (per AquaBlend MILP Configuration, Section 3)

---

## 1. Published Source Figures

Two real, publicly available figures are combined to build a real-world daily demand estimate for Greater Melbourne.

### 1.1 Population
- **Value:** 5,350,705 people (Greater Melbourne, Estimated Resident Population)
- **Source:** Australian Bureau of Statistics, Regional Population release
- **Publication date:** 27 March 2025 (reference period: as at 30 June 2024)

### 1.2 Residential water use per person
- **Value:** 166 litres per person per day
- **Source:** Melbourne Water, Melbourne's Annual Water Outlook (quarterly update)
- **Publication date:** update published circa March 2026, reporting on the 12 months to 1 March 2026

Note on scope: this is residential (household) use only. It excludes non-residential (commercial, industrial, non-revenue/leakage) water use, so the resulting total is a conservative lower bound on Melbourne's true total daily demand, not a complete figure. This limitation is carried through explicitly below.

---

## 2. Original Published Figure

Total real-world estimated residential demand for Greater Melbourne:

```
5,350,705 people x 166 L/person/day = 888,217,030 L/day
```

Converting litres to megalitres (1 ML = 1,000,000 L):

```
888,217,030 L/day / 1,000,000 = 888.22 ML/day
```

**Original published figure: approximately 888 ML/day, residential-only, Greater Melbourne.**
**Time basis: ML/day.**

This is the number before any toy-model scaling. It is not the number used in the model.

---

## 3. Scaling to the Toy Model

The toy model is a 3-reservoir, 1-facility, 1-zone proof-of-concept (AquaBlend MILP Configuration, Section 3), not a full representation of Melbourne's bulk water system. Using the real ~888 ML/day figure directly would be inconsistent with a small, hand-checkable toy model, and would not test the MILP logic (source selection, capacity limits, activation) in a meaningful way, since a single reservoir like Thomson could absorb almost all of it without any interesting trade-off.

**Scaling approach:** the real-world figure is reduced so that the toy demand sits inside the combined capacity of the three toy reservoirs, while exceeding what any single one of the smaller two could supply alone (matching the Task 1 requirement that demand be sized so no single source can meet it alone).

To check this reasonably, the three example reservoirs' real bulk storage volumes were converted into placeholder daily-extractable capacities, since real safe-yield/withdrawal-rate data is not yet sourced (per AquaBlend MILP Configuration, Section 3, "Source capacity clarification"). A placeholder ratio of 0.1% of active/usable storage per day was applied, purely to sanity-check order of magnitude — this ratio is **not** a published figure and is flagged as an assumption.

| Reservoir | Real usable/active storage | Placeholder daily capacity (0.1%/day) |
|---|---|---|
| Silvan | 40,580 ML | ~40.6 ML/day |
| Sugarloaf | 96,253 ML | ~96.3 ML/day |
| Thomson | 1,123,090 ML | ~1,123.1 ML/day |

Combined placeholder capacity: approximately 1,260 ML/day.

Scaling the real 888 ML/day figure down by a factor of approximately 1/13.7 gives a toy demand of about 65 ML/day. At 65 ML/day:
- Silvan alone (~40.6 ML/day) cannot meet demand -> forces blending, matching the toy model's purpose.
- Silvan + Sugarloaf together (~136.8 ML/day) can meet demand, so the scenario is feasible with more than one source active.
- The value stays well below the combined placeholder capacity, leaving headroom for dry-year/high-demand scenario testing (Tasks 10-11) without immediate infeasibility.

**Final toy-model value: 65 ML/day.**

---

## 4. Final Value for the Schema

```
demand_zones[].required_volume_ML = 65
```

**Time basis: ML/day** (consistent with the source capacity and cost fields, which are also expressed per day/per ML).

---

## 5. Reasonableness Check

- 65 ML/day sits between the smallest (Silvan, ~40.6 ML/day) and second-smallest (Sugarloaf, ~96.3 ML/day) placeholder reservoir capacities, so the toy scenario always requires blending across at least two sources — this is the intended behaviour for a MILP that tests source selection and blending logic.
- 65 ML/day is well below the combined placeholder capacity (~1,260 ML/day), so the baseline scenario itself should remain feasible, leaving room for the dry-year and high-demand scenarios (Tasks 10-11) to push the model toward infeasibility deliberately.

---

## 6. Limitations and Open Items

- The 166 L/person/day figure is residential-only. Total Melbourne demand (including commercial, industrial, and non-revenue water) is higher than 888 ML/day; this document intentionally uses the residential figure because it has a clean, citable per-capita basis, but it is a lower bound, not a total.
- The 0.1%/day placeholder extraction ratio used in Section 3 is **not** a published safe-yield figure. It exists only to sanity-check that 65 ML/day is a reasonable toy value against the three example reservoirs' real storage volumes. Real per-source daily safe-yield/withdrawal-rate data has not yet been sourced, per the AquaBlend MILP Configuration's own documented gap.
- This document does not set the official `capacity_ML` values for `sources.json` — that belongs to whoever finalises the toy-model source configuration (Tasks 1-3 owners / Data Engineering). The placeholder capacities in Section 3 are for reasonableness-checking only and should be reconciled against the actual source configuration once it is confirmed, to avoid duplicated research.
- Data Engineering should be contacted to confirm whether Melbourne Water's Open Data Hub already publishes a more precise per-source safe-yield or daily withdrawal figure, which would replace the placeholder ratio used here.

---

## 7. Sources

- Australian Bureau of Statistics, Regional Population (Greater Melbourne ERP, 30 June 2024), released 27 March 2025.
- Melbourne Water, Melbourne's Annual Water Outlook, quarterly update (residential water use, 12 months to 1 March 2026), published circa March 2026.
- Melbourne Water, Water Storage Reservoirs page (reservoir capacities and network links).
- Wikipedia, Silvan Reservoir / Sugarloaf Reservoir / Sugarloaf Dam / Thomson Dam (storage capacity figures, cross-checked against Melbourne Water's own descriptions).
