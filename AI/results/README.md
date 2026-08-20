# Results

## Task 28: Sensitivity and Value-of-Data Ranking

### Overview

The sensitivity ranking module processes verified
`sensitivity_to_key_assumptions` information from the Results JSON and
cross-references relevant source provenance from `data_flags.sources`.

The module does not modify MILP results or create new impact values.

### Ranking Behaviour

Sensitivity entries are ranked only when the available information supports a
fair comparison.

The current Results JSON provides sensitivity impacts mainly as free-text
descriptions. There is currently no agreed fixed priority rule such as
feasibility > quality > cost.

The module therefore does not invent scores or priorities that are not
supported by the Results JSON.

### Insufficient-Data Behaviour

When sensitivity information is missing, incomplete, or does not support a fair
comparison, the module returns `INSUFFICIENT_DATA` instead of creating an
unsupported ranking.

Example:

```json
{
  "status": "INSUFFICIENT_DATA",
  "rankings": [],
  "reason": "Sensitivity information does not support a fair ranking."
}
