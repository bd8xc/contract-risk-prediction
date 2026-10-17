"""Root-level wiring for the independent COI, LE, CR, and CL agents."""
from __future__ import annotations

import logging
import re
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from coi.conflict_agent import ConflictOfInterestAgent
from le import LexState, LitigationExposureAgent
from groq_client import groq_is_configured
from ingestion_pipeline.document_input import MAX_FILE_BYTES, extract_text

ROOT = Path(__file__).resolve().parent
CR_ROOT = ROOT / "agents" / "cr"
CR_CHECKPOINT = CR_ROOT / "checkpoints" / "best_model.pt"
if str(CR_ROOT) not in sys.path:
    sys.path.insert(0, str(CR_ROOT))
from agents.cl.confidentiality_leakage.agent import ConfidentialityLeakageAgent
from processing.clause_segmenter import ClauseSegmenter

router = APIRouter()
logger = logging.getLogger(__name__)
_cr_lock = threading.Lock()
_cr_predictor: Any | None = None


class ContractFeatures(BaseModel):
    deal_size: float = Field(ge=50_000, le=5_000_000)
    liability_cap: int = Field(ge=0, le=1)
    auto_renewal: int = Field(ge=0, le=1)
    jurisdiction_risk: float = Field(ge=1, le=10)
    indemnification_clause: int = Field(ge=0, le=1)
    dispute_history: int = Field(ge=0, le=1)
    governing_law_clarity: float = Field(ge=1, le=5)


class AnalyzeRequest(BaseModel):
    doc_id: str | None = Field(default=None, max_length=128)
    client_entity: str = Field(min_length=1, max_length=200)
    counterparty_entity: str = Field(min_length=1, max_length=200)
    contract_entities: list[str] = Field(default_factory=list, max_length=13)
    contract_text: str = Field(min_length=40, max_length=120_000)
    features: ContractFeatures
    # An externally measured template deviation. CR risk labels are not interchangeable.
    clause_deviation_override: float | None = Field(default=None, ge=0, le=1)


@router.post("/extract", tags=["Ingestion"])
async def extract_document(file: UploadFile = File(...)) -> dict[str, str]:
    content = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    try:
        return {"text": extract_text(file.filename or "", content)}
    except (ValueError, UnicodeError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _clauses(text: str, *, max_clauses: int | None = 12) -> list[dict[str, str]]:
    """Use CR's segmenter and retain text before numbered clauses."""
    numbered = re.search(r"(?m)^\s*\d+(?:\.\d+)*\.?\s+", text)
    try:
        segments = ClauseSegmenter().segment(text)
        if segments and numbered:
            clauses = [
                {"id": str(item.get("clause_number") or item.get("index") or i),
                 "section": str(item.get("section") or ""),
                 "text": str(item.get("text", "")).strip()}
                for i, item in enumerate(segments, 1)
                if str(item.get("text", "")).strip()
            ]
            preamble = re.sub(r"\s+", " ", text[:numbered.start()]).strip()
            if preamble:
                clauses.insert(0, {"id": "P0", "section": "", "text": preamble})
            if clauses:
                return clauses if max_clauses is None else clauses[:max_clauses]
    except Exception:
        logger.exception("CR clause segmentation failed; using paragraph fallback")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if max_clauses is not None:
        paras = paras[:max_clauses]
    return [{"id": str(i), "section": "", "text": p} for i, p in enumerate(paras, 1)] or [{"id": "1", "section": "", "text": text.strip()}]


def _cl_clauses(text: str) -> list[dict[str, str]]:
    """Keep every paragraph, including preambles and short sensitive lines."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    clauses = []
    for index, paragraph in enumerate(paragraphs, 1):
        number = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", paragraph)
        clauses.append({"clause_id": number.group(1) if number else f"P{index}",
                        "section": "", "text": paragraph})
    return clauses


def _cr_clauses(text: str) -> tuple[list[dict[str, str]], int]:
    clauses = _clauses(text, max_clauses=None)
    return clauses[:12], max(0, len(clauses) - 12)


def _run_cr(text: str) -> dict[str, Any]:
    if not CR_CHECKPOINT.is_file():
        return {"status": "unavailable", "reason": "Fine-tuned LegalBERT checkpoint is missing.",
                "checkpoint": "agents/cr/checkpoints/best_model.pt", "clauses": []}
    global _cr_predictor
    with _cr_lock:
        if _cr_predictor is None:
            try:
                from models.inference import ContractRiskPredictor

                _cr_predictor = ContractRiskPredictor()
            except Exception as exc:
                return {"status": "unavailable", "reason": f"CR could not start: {type(exc).__name__}: {exc}"}
        clauses, omitted = _cr_clauses(text)
        results = []
        for clause in clauses:
            try:
                prediction = _cr_predictor.predict(clause["text"])
                results.append({
                    "clause_id": clause["id"],
                    "model": prediction,
                })
            except Exception as exc:
                results.append({"clause_id": clause["id"], "status": "error", "reason": str(exc)})
        failed = sum(result.get("model", {}).get("prediction") not in {"Seed", "Low", "Medium", "High"}
                     for result in results)
        common = {
            "mode": "legalbert",
            "checkpoint": "agents/cr/checkpoints/best_model.pt",
            "clauses": results,
            "omitted_clause_count": omitted,
            "model_note": "Seed is a baseline class, not a Low-risk label. Model scores are not calibrated probabilities.",
        }
        if not results or failed or omitted:
            return {**common, "status": "incomplete",
                    "reason": f"CR did not classify {failed + omitted or 1} clause(s)"}
        return {**common, "status": "complete"}


def _run_coi(request: AnalyzeRequest, doc_id: str):
    return ConflictOfInterestAgent().run(
        client_entity=request.client_entity,
        counterparty_entity=request.counterparty_entity,
        doc_id=doc_id,
        contract_entities=request.contract_entities,
    )


def _run_le(request: AnalyzeRequest, conflict_flag: int, deviation: float) -> dict[str, Any]:
    state = LexState(
        contract_text=request.contract_text,
        entities=request.features.model_dump(),
        graph_results={"conflict_flag": conflict_flag},
        clause_deviation_score=deviation,
    )
    prediction = LitigationExposureAgent().predict_with_explanation(state)
    prediction["basis"] = "synthetic_training"
    prediction["interpretation"] = "A synthetic-model score, not a validated real-world litigation probability."
    return prediction


def _run_cl(text: str, doc_id: str) -> dict[str, Any]:
    """Run the independent CL detectors on the shared contract clauses."""
    report = ConfidentialityLeakageAgent().analyze(doc_id, clauses=_cl_clauses(text))
    result = report.model_dump()
    for finding in result["findings"]:
        finding["value"] = "[redacted]"
    for activity in result["processing_activity"]:
        activity.pop("value", None)
    return result


def _decision(coi: Any, cr: dict[str, Any], cl: dict[str, Any], le: dict[str, Any] | None) -> dict[str, Any]:
    """Explain why a person must review this run without inventing a combined score."""
    reasons = []
    if coi is None or coi.status != "complete":
        reasons.append("COI graph evidence or entity coverage is incomplete.")
    elif coi.conflict_detected:
        reasons.append("COI found a verified conflict path.")
    if cr.get("status") != "complete":
        reasons.append("CR classification is incomplete or unavailable.")
    else:
        reasons.append("CR labels are model risk signals and require human interpretation.")
    if cl.get("status") != "complete":
        reasons.append("CL did not complete.")
    elif cl.get("sensitive_data_detected"):
        reasons.append("CL detected sensitive information for review.")
    if le is None:
        reasons.append("LE could not run with the required verified inputs.")
    else:
        reasons.append("LE was trained on synthetic labels and is not outcome-calibrated.")
    return {
        "disposition": "human_review_required",
        "reasons": reasons,
        "limitations": [
            "A negative COI search covers only the configured graph.",
            "This workflow does not make a legal approval decision.",
        ],
    }


@router.get("/status", tags=["Status"])
def status() -> dict[str, Any]:
    try:
        from coi.graph_manager import get_graph

        get_graph().driver.verify_connectivity()
        coi = "ready"
    except Exception:
        coi = "unavailable"
    try:
        from agents.cl.confidentiality_leakage.detectors.ner_detector import _load_nlp

        cl_ner = "spacy" if _load_nlp() is not None else "regex_fallback"
        cl = "ready"
    except Exception:
        cl, cl_ner = "degraded", "regex_fallback"
    return {
        "coi": coi,
        "le": "ready" if (ROOT / "agents" / "le" / "litigation_model.joblib").is_file() else "unavailable",
        "cr": "ready" if CR_CHECKPOINT.is_file() else "missing_model",
        "cl": cl,
        "cl_ner": cl_ner,
        "groq": "configured" if groq_is_configured() else "missing_key",
    }


@router.post("/analyze", tags=["Review"])
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    doc_id = (request.doc_id or f"web-{uuid.uuid4().hex[:12]}" ).strip()
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="lexguard") as pool:
        coi_future = pool.submit(_run_coi, request, doc_id)
        cr_future = pool.submit(_run_cr, request.contract_text)
        cl_future = pool.submit(_run_cl, request.contract_text, doc_id)
        try:
            coi_report = coi_future.result()
        except Exception as exc:
            coi_report = None
            coi_error = f"{type(exc).__name__}: {exc}"
        else:
            coi_error = None
        try:
            cr_report = cr_future.result()
        except Exception as exc:
            cr_report = {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
        try:
            cl_report = cl_future.result()
            cl_report["status"] = "complete"
        except Exception as exc:
            cl_report = {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}

    deviation = request.clause_deviation_override
    deviation_source = "manual_template_measurement" if deviation is not None else None

    le_report = None
    le_status = "skipped"
    if coi_report is None or coi_report.status != "complete":
        le_status = "skipped: COI did not complete entity resolution and graph search"
    elif deviation is None:
        le_status = "skipped: no approved template deviation is available; enter an externally measured value to run LE"
    else:
        try:
            le_report = _run_le(request, int(coi_report.conflict_flag), deviation)
            le_status = "complete"
        except Exception as exc:
            le_status = f"unavailable: {type(exc).__name__}: {exc}"

    component_states = [
        "complete" if coi_report is not None and coi_report.status == "complete" else "incomplete",
        cr_report.get("status", "incomplete"),
        "complete" if le_report is not None else "incomplete",
        cl_report.get("status", "incomplete"),
    ]
    overall = "complete" if all(s == "complete" for s in component_states) else "partial"
    decision = _decision(coi_report, cr_report, cl_report, le_report)
    return {
        "doc_id": doc_id,
        "status": overall,
        "coi": coi_report.to_dict() if coi_report is not None else {"status": "unavailable", "reason": coi_error},
        "cr": cr_report,
        "cl": cl_report,
        "le": le_report,
        "le_status": le_status,
        "clause_deviation_score": deviation,
        "clause_deviation_source": deviation_source,
        "review_required": True,
        "decision": decision,
    }
