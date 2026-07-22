
# AquaBlend

AquaBlend is a mathematical optimisation framework that helps drinking-water providers select, blend, and treat water from multiple sources across Victoria. The project uses Mixed Integer Linear Programming (MILP) to recommend cost-effective source blending and treatment strategies while maintaining drinking-water safety, regulatory compliance, and operational feasibility.

This is a SIT Capstone project (Product Owner: Dr Atabak Elmi), currently in its public-data proof-of-concept phase.

## Project Overview

Different Victorian water sources, reservoirs, rivers, and groundwater, have different mineral and quality profiles. AquaBlend explores whether intelligently selecting and blending these sources before or during treatment can reduce the amount of added chemicals and treatment required, lowering operating costs while keeping water safe and compliant.

The project starts with a public-data proof-of-concept (Scope 1) and is designed to evolve toward an operational model using real water corporation data in future trimesters.

## Team Structure

The project is organised into four teams, each owning a distinct part of the pipeline:

| Team | Folder | Responsible For |
|---|---|---|
| Optimisation (MILP) | `MILP/` | The mathematical formulation and optimisation model. Takes in water source data, demand, and quality constraints, and outputs a recommended blend, cost breakdown, and constraint status. This is the core decision engine the rest of the project builds around |
| Data Engineering | `Data_sci_scripts/` | Sourcing, cleaning, and documenting the real datasets the model runs on (reservoir, river, and groundwater data, water quality readings, etc.), and maintaining a clear record of what's been collected and what's still outstanding |
| AI and Analysis | `AI/` | Demand forecasting, anomaly detection, and any applied AI/LLM features (e.g. natural-language summaries or a Q&A layer over model results) |
| App & Delivery | `Frontend/` and `Backend/` | The dashboard and product interface. Consumes the MILP model's output and presents it to users through a working web application, frontend UI plus backend routes/services/database |

Data flows roughly like this: **Data Engineering** collects and cleans source data → **AI and Analysis** adds forecasts/insights on top → **MILP** uses both to compute the optimal blend → **App & Delivery** presents the final result to the user.
## Repository Structure

```
Aqua-Blend/
├── MILP/                  # Optimisation model: formulation, code, and documentation
├── AI/                    # AI and Analysis models and documentation
├── Data_sci_scripts/      # Data cleaning scripts and dataset documentation
├── Frontend/              # Dashboard frontend source
├── Backend/               # Dashboard backend: routes, services, controllers, ORM
└── readme.md              # This file
```

**Please only make changes inside the folder your team owns.** If something needs to change in another team's folder, raise it with that team directly rather than editing it yourself.

## Workflow

We are using GitHub as the single source of truth for all code and documentation, including the MILP formulation doc.

- Clone the repo and make your changes locally within your team's folder
- We are **not** merging into `main` every week. Once everyone on your team has finished their part for a given phase, create a new branch, push all changes to that branch, and a Pull Request will be opened for review at the end of the trimester
- Keep documentation (`Documentation.md`, `timeline.md`, etc.) inside your team's folder up to date as you go, not just at the end
- Never commit sensitive data: API keys, credentials, connection strings, or `.env` files. Each folder should have its own `.gitignore` where relevant. If sensitive data is accidentally committed, flag it immediately rather than just deleting it, since it may still exist in git history

## Contact

Mentor: Saeedeh Javadi
Product Owner: Dr Atabak Elmi

---

**One important rule for everyone:** only make changes inside the folder your team owns. If something in another team's folder needs to change, don't edit it directly, raise it with that team instead so they can make the change themselves. This keeps ownership clear and avoids conflicting or accidental edits across teams.