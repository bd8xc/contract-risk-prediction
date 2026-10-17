# Agents

Each agent owns one risk signal. The root `coordinator.py` runs COI, CR, and CL for an assessment, then runs LE only when COI has a complete result and a measured template deviation is supplied.

| Directory | Responsibility |
|---|---|
| [coi](coi/README.md) | Neo4j conflict of interest analysis |
| [le](le/README.md) | XGBoost litigation exposure and SHAP explanation |
| [cr](cr/README.md) | Clause risk classification and legal retrieval |
| [cl](cl/README.md) | Confidentiality and personal data detection |

Shared environment settings are in the repository root `.env`. Install COI and LE as editable packages through the root `requirements.txt`.
