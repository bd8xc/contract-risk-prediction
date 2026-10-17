"""Direct text endpoints for CR and CL in the unified API."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import coordinator
from agents.cl.confidentiality_leakage.schemas import ConfidentialityReport

router = APIRouter()


class ContractTextRequest(BaseModel):
    contract_text: str = Field(min_length=1, max_length=120_000)
    doc_id: str | None = Field(default=None, max_length=128)


class CRReport(BaseModel):
    status: str
    clauses: list[dict[str, Any]] = Field(default_factory=list)
    omitted_clause_count: int = 0
    mode: str | None = None
    reason: str | None = None
    source_warning: str | None = None
    checkpoint: str | None = None
    model_note: str | None = None


class CLReport(ConfidentialityReport):
    status: Literal["complete"] = "complete"


@router.post("/cr/analyze", tags=["CR"], response_model=CRReport)
def analyze_contract_risk(request: ContractTextRequest) -> dict[str, Any]:
    """Classify contract clauses with the fine-tuned LegalBERT checkpoint."""
    return coordinator._run_cr(request.contract_text)


@router.post("/cl/analyze", tags=["CL"], response_model=CLReport)
def analyze_confidentiality(request: ContractTextRequest) -> dict[str, Any]:
    """Scan every paragraph; returned sensitive values are redacted."""
    doc_id = (request.doc_id or f"api-{uuid.uuid4().hex[:12]}").strip()
    if not doc_id:
        raise HTTPException(status_code=422, detail="doc_id cannot be blank")
    try:
        return {"status": "complete", **coordinator._run_cl(request.contract_text, doc_id)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CL unavailable: {type(exc).__name__}: {exc}") from exc
