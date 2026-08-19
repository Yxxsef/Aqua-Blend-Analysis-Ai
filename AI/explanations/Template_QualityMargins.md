# Template_QualityMargins.md

AquaBlend | Analysis & AI | Water-quality and safety-margin explanation template

## Purpose

Turn the optimiser's numeric water-quality results into a plain-language statement of
whether the treated water passed its quality requirements, and which parameter sat
closest to its allowed limit.

The headline is always the **smallest positive safety margin** — the tightest parameter —
because that is the one most at risk of a future breach. The widest margin is optional
secondary detail, not the main message.

## Input

Reads `water_quality.after_treatment` from the current Results JSON. Each parameter object provides:

- `value`
- `unit`
- `constraint_min`
- `constraint_max`
- `status` (PASS / FAIL)
- `safety_margin_percent`

The template **consumes `safety_margin_percent` as given** by post-processing; it does not
recompute it. Interpretation:

- higher % = more headroom (safer)
- small positive % = close to a limit (at risk)
- **negative % = value is outside its allowed range = a violation**

## Selection logic

1. Read every parameter under `after_treatment`.
2. Classify each: **PASS** if `status` is PASS and `safety_margin_percent` >= 0;
   **VIOLATION** if `status` is FAIL or `safety_margin_percent` < 0.
3. Overall result = PASS only if every parameter passes; otherwise FAIL.
4. **Tightest parameter** = the passing parameter with the *smallest* `safety_margin_percent`.
   This is the headline.
5. **Widest parameter** = the passing parameter with the *largest* `safety_margin_percent`.
   Optional secondary line only.
6. If any violations exist, they are reported first and take priority over the
   tightest-margin headline.

## Unit rules

- **pH** — report as a plain number labelled pH. It carries no concentration unit.
  Never mg/L, never %.
- **Alkalinity** — mg/L CaCO3.
- **Turbidity** — NTU.
- For any parameter, echo the `unit` field from the JSON, but validate it against the three
  rules above and flag a mismatch rather than printing a wrong unit.

## Missing parameters

If an expected parameter is absent from `after_treatment`, do **not** assume it passed.
State it explicitly:

> {parameter_name} was not reported in the results and could not be assessed.

## Estimated values

Cross-check `data_flags.estimated_fields`. If a reported parameter (or a source feeding the
blend) is flagged as estimated, append:

> Note: this assessment relies on estimated data for {field} and should be treated as
> provisional.

## Output templates

**All parameters passed**

> All tested quality parameters passed. {tightest_parameter_name} was closest to its limit,
> with a safety margin of {safety_margin_percent}%.

Optional secondary line:

> The widest margin was on {widest_parameter_name} at {safety_margin_percent}%.

**One or more parameters failed (negative or FAIL)**

> Not all quality parameters passed. {violation_parameter_name} breached its allowed range:
> {value} {unit} against a permitted {constraint_min}-{constraint_max} {unit}
> (safety margin {safety_margin_percent}%). This is treated as a violation and must be
> resolved before the blend is acceptable.

List each violation separately if there is more than one.

**Missing parameter (append as needed)**

> {parameter_name} was not reported in the results and could not be assessed.

**Estimated-data note (append as needed)**

> Note: this assessment relies on estimated data for {field} and should be treated as
> provisional.

## Worked test against the reference JSON

Using the current reference Results JSON, `water_quality.after_treatment` gives:

| Parameter  | Value | Unit         | Status | safety_margin_percent |
| ---------- | ----- | ------------ | ------ | --------------------- |
| pH         | 7.4   | pH           | PASS   | 21.4                  |
| alkalinity | 52.3  | mg/L CaCO3   | PASS   | 47.7                  |
| turbidity  | 2.1   | NTU          | PASS   | 58.0                  |

All three pass, so overall result = PASS. Smallest positive margin = **pH at 21.4%**, so pH
is the headline. Widest = turbidity at 58.0%.

Generated output:

> All tested quality parameters passed. pH was closest to its limit, with a safety margin of
> 21.4%.

Optional secondary line:

> The widest margin was on turbidity at 58.0%.

Unit check: pH printed with no concentration unit, alkalinity would read mg/L CaCO3,
turbidity NTU — all consistent with the rules above. No `after_treatment` parameter is
flagged in `data_flags.estimated_fields`, so no provisional note is added for this scenario.