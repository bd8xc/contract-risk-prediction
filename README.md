# LexGuard local review app

The four agents live under `agents/coi`, `agents/le`, `agents/cr`, and `agents/cl`. The shared document indexing pipeline lives under `ingestion_pipeline/ldi`; the web app and coordinator stay at the repository root. COI, CR, and CL run on the same request. LE runs when COI has a verified graph result and an externally measured template deviation is supplied. CL scans contract text for personal and business-confidential information and reports a risk score with findings.

```text
Sem7/
  agents/
    coi/   # conflict of interest
    le/    # litigation exposure
    cr/    # contract risk
    cl/    # confidentiality leakage
  ingestion_pipeline/
    document_input.py  # TXT, PDF, and DOCX upload extraction
    ldi/   # optional document indexing and search
  app.py, coordinator.py, groq_client.py
  .env
```

## Architecture map

Directory guides: [agents](agents/README.md), [ingestion pipeline](ingestion_pipeline/README.md), [web interface](web/README.md), and [tests](tests/README.md). Each maintained subdirectory has its own `README.md`.

| Diagram component | Existing code |
|---|---|
| Contract parsing and clause extraction | `ingestion_pipeline/document_input.py`, `ingestion_pipeline/ldi/` |
| Structured contract state and agent coordination | `coordinator.py` |
| Conflict, confidentiality, clause risk, litigation exposure | `agents/coi/`, `agents/cl/`, `agents/cr/`, `agents/le/` |
| Legal knowledge and retrieval | `agents/cr/knowledge_base/`, `agents/cr/rag/`, optional `ingestion_pipeline/ldi/search/` |
| Graph and optional vector storage | COI Neo4j, LDI ChromaDB |

The current implementation uses Groq for its grounded LLM calls. The diagram's local Qwen model, persistent Contract/LexState store, and report store are not implemented here. The coordinator returns the component reports and review decision in the API response. Those parts require separate feature work beyond this code organization change.

## API and Swagger

The root app serves one Swagger UI at `/docs`. It includes the combined `/api/analyze` review, direct COI (`/api/coi/check`), CR (`/api/cr/analyze`), CL (`/api/cl/analyze`), and LE (`/api/le/predict`) test routes, the COI-to-LE `/api/risk/assess` route, and ingestion/indexed-search routes under `/api/ingestion/`. The Atelier frontend starts at `/`, with a guided review at `/review`, a tab-local report at `/results`, and individual agents under `/workspaces`. The previous JSON dashboard is at `/advanced`. Swagger also exposes the multipart upload endpoints.

The standalone LE route accepts caller-supplied graph results for isolated model testing. Use `/api/risk/assess` or `/api/analyze` when LE must receive a COI result from this run. Indexed search and indexed CL require documents to be embedded first. On `/advanced`, select either indexed endpoint and upload a PDF or DOCX to index it through `/api/ingestion/embed-multi/`; the indexed CL sample then uses that filename as `doc_id`. Uploads on the guided review and specialist pages use `/api/extract` and do not add documents to the vector index.

## Start

Use Python 3.12. From this folder:

Copy `.env.example` to `.env` and set `NEO4J_PASSWORD` and `GROQ_API_KEY` before starting Docker. This is the only environment file used by the app, agents, and Docker Compose.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose --env-file .env -f agents/coi/compose.yaml up -d
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>.

You can paste contract text or load a TXT, PDF, or DOCX file. Upload extraction runs in memory and fills the editable text field. Check extracted text before assessment. Scanned PDFs need OCR outside this app. A file is not automatically added to the COI graph. The guided review keeps its latest result in the browser tab's session storage so `/results` can display it; this is not a server report store.

## CR setup

The root CR endpoints classify clauses with the fine-tuned LegalBERT checkpoint at `agents/cr/checkpoints/best_model.pt`. They do not call Groq or retrieve legal text. If the checkpoint is missing, CR reports `unavailable`; it does not substitute an LLM assessment. LE does not infer template deviation from CR labels. To train the model again:

```powershell
Push-Location agents/cr
..\..\.venv\Scripts\python.exe prepare_validation.py
..\..\.venv\Scripts\python.exe train.py
Pop-Location
```

Training downloads LegalBERT from Hugging Face and can take a long time on CPU. The generated validation split keeps clauses from one source document together. Training writes the best checkpoint under `agents/cr/checkpoints/best_model.pt`.

COI's optional document extractor uses Groq through the shared root `.env`. The root CR endpoints do not. LegalBERT inference may download the base tokenizer and model assets from Hugging Face on first use. LE still requires a completed COI check.

LegalBERT returns one of `Seed`, `Low`, `Medium`, or `High` for each attempted segment. `Seed` is the model's baseline/source-pattern class, not a Low-risk label. It is displayed as Baseline and remains a completed model classification. Its softmax score is not a calibrated probability. The optional legacy `agents/cr/analyze_clause.py` research script still contains an LLM explanation workflow, but the root API does not invoke it.

CR analyzes up to 12 clauses per request. If the contract has more clauses or any clause fails, the response reports `incomplete`. LE uses an externally measured template deviation from 0 to 1 entered in the form; CR labels are not converted into that value. LE's model was trained on synthetic labels, so its percentage is a model score, not a calibrated real-world litigation probability.

## CL setup

The root app passes every paragraph, including short text and preambles, directly to CL. The root `requirements.txt` includes spaCy and the optional indexed LDI dependencies. CL's deterministic detectors still run if the spaCy model is unavailable. The root integration does not use ChromaDB or a separate CL server. See `agents/cl/README.md` for the standalone indexed pipeline.

## Data handling

The app does not write submitted contract text or analysis responses to disk. The root CR endpoints run locally and do not send clauses to Groq. CL findings are redacted in the API response. Do not submit confidential material unless your testing approval and data policy permit this. COI searches the shared Neo4j graph. Imported legacy facts have no source clauses and are marked unverified. An unverified conflict is a review lead and cannot set LE's conflict flag. A negative search covers only the configured graph; it does not prove that every relevant relationship was recorded. Every assessment therefore calls for human review, with explicit reasons in the response.

The API is for local use. It has no authentication. Do not expose it to a network without adding access controls and a data policy.

