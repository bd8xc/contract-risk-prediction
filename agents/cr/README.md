# Contract Risk (CR)

The root CR endpoints segment contract text and classify up to 12 segments with the fine-tuned `checkpoints/best_model.pt` LegalBERT model. They do not call Groq or use retrieved legal context. A missing checkpoint makes CR unavailable. The `Seed` class is displayed as Baseline; it is not a Low-risk judgment. Model scores are uncalibrated. The separate `analyze_clause.py` research script retains an optional LLM explanation workflow and is not called by the root API.

The unified Swagger UI exposes direct text analysis at `/api/cr/analyze` and the coordinated run at `/api/analyze`.

Install the root `requirements.txt`. To prepare a grouped validation split and train, run from `agents/cr`:

```powershell
..\..\.venv\Scripts\python.exe prepare_validation.py
..\..\.venv\Scripts\python.exe train.py
```

`models/` contains training and inference code, `processing/` handles clauses and risk checks, `rag/` retrieves legal context, and `reporting/` builds exports. Training data and model artifacts are kept alongside this agent. Training may download Hugging Face models.
