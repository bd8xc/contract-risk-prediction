"""
Pydantic schemas for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    question: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Legal question (5-5000 characters)"
    )

class SafetyChecks(BaseModel):
    """Safety verification results with robustness metrics"""
    rules_passed: bool
    model_verified: bool
    violations: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0, description="Robustness score 0-100")
    hallucination_risk: str = Field(default="unknown", description="low|medium|high")
    claimed_facts: List[Dict[str, Any]] = Field(default_factory=list)
    # Enhanced robustness fields
    known_hallucinations: int = Field(default=0, description="Count of detected hallucinations")
    logical_contradictions: int = Field(default=0, description="Count of logical inconsistencies")
    recommendations: List[str] = Field(default_factory=list, description="Review recommendations")

class ChatResponse(BaseModel):
    """Response schema for chat endpoint"""
    question: str
    answer: str
    safety_checks: SafetyChecks
    debug_trace: List[str] = Field(default_factory=list)
    status: str = "success"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    status: str = "error"
    debug_trace: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class COIRequest(BaseModel):
    """Request schema for COI-only endpoint"""
    doc_id: str = Field(..., min_length=1, description="Document identifier")
    client_entity: str = Field(..., min_length=1, description="Primary client entity")
    counterparty_entity: str = Field(..., min_length=1, description="Primary counterparty entity")
    contract_entities: List[str] = Field(default_factory=list, max_length=13, description="Other entities extracted from contract")
    additional_entities: List[str] = Field(default_factory=list, max_length=13, description="Optional extra entities to include")


class COIResponse(BaseModel):
    conflict_detected: bool
    conflict_path: List[str] = Field(default_factory=list)
    severity: str
    status: str
    conflict_flag: Optional[int] = None
    skipped_reason: Optional[str] = None
    unresolved_entities: List[str] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    review_required: bool
    run_metadata: Dict[str, Any] = Field(default_factory=dict)


class LitigationEntities(BaseModel):
    """Structured features required by the Litigation Exposure agent."""
    deal_size: float = Field(..., ge=50_000, le=5_000_000)
    liability_cap: int = Field(..., ge=0, le=1)
    auto_renewal: int = Field(..., ge=0, le=1)
    jurisdiction_risk: float = Field(..., ge=1, le=10)
    indemnification_clause: int = Field(..., ge=0, le=1)
    dispute_history: int = Field(..., ge=0, le=1)
    governing_law_clarity: float = Field(..., ge=1, le=5)


class LitigationRiskRequest(BaseModel):
    """Request schema for LE-only prediction endpoint."""
    entities: LitigationEntities
    clause_deviation_score: float = Field(..., ge=0, le=1)
    graph_results: Dict[str, Any]


class LitigationRiskResponse(BaseModel):
    """Response schema for Litigation Exposure predictions."""
    litigation_probability: float
    risk_level: str
    features_used: Dict[str, float] = Field(default_factory=dict)
    shap_explanation: Dict[str, float] = Field(default_factory=dict)
    model_fingerprint: Optional[str] = Field(
        default=None,
        description=(
            "Identifies which litigation_model.joblib artifact produced this "
            "probability/explanation pair. Compare across responses to catch "
            "a model file changing under a live deployment."
        ),
    )


class CombinedRiskRequest(BaseModel):
    """Request schema that runs COI first and feeds its flag into LE."""
    doc_id: str = Field(..., min_length=1, description="Document identifier")
    client_entity: str = Field(..., min_length=1, description="Primary client entity")
    counterparty_entity: str = Field(..., min_length=1, description="Primary counterparty entity")
    contract_entities: List[str] = Field(default_factory=list, max_length=13, description="Other entities extracted from contract")
    additional_entities: List[str] = Field(default_factory=list, max_length=13, description="Optional extra entities to include")
    litigation_entities: LitigationEntities
    clause_deviation_score: float = Field(..., ge=0, le=1)


class CombinedRiskResponse(BaseModel):
    """Combined response for COI plus Litigation Exposure."""
    coi: COIResponse
    litigation: Optional[LitigationRiskResponse] = None
    status: str = "success"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

__all__ = [
    'ChatRequest',
    'ChatResponse',
    'COIRequest',
    'COIResponse',
    'CombinedRiskRequest',
    'CombinedRiskResponse',
    'ErrorResponse',
    'HealthResponse',
    'LitigationEntities',
    'LitigationRiskRequest',
    'LitigationRiskResponse',
    'SafetyChecks'
]