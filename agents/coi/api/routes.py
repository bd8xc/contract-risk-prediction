"""Synchronous endpoints run blocking graph work in FastAPI's thread pool."""
from fastapi import APIRouter, HTTPException
from ..conflict_agent import ConflictOfInterestAgent
from ..le_integration import assess_litigation_after_coi, predict_litigation
from .schemas import (COIRequest, COIResponse, CombinedRiskRequest,
                      CombinedRiskResponse, LitigationRiskRequest, LitigationRiskResponse)

router = APIRouter()


def get_agent():
    return ConflictOfInterestAgent()


@router.post("/coi/check", response_model=COIResponse, tags=["COI"])
def coi_check(request: COIRequest):
    try:
        return get_agent().run(**request.model_dump()).to_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/risk/assess", response_model=CombinedRiskResponse, tags=["COI + LE"])
def risk_assess(request: CombinedRiskRequest):
    try:
        return assess_litigation_after_coi(**request.model_dump(), coi_agent=get_agent())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/le/predict", response_model=LitigationRiskResponse, tags=["LE"],
             description="Isolated LE model test using caller-supplied graph_results. Use /api/risk/assess or /api/analyze for a COI-verified handoff.")
def litigation_predict(request: LitigationRiskRequest):
    try:
        return predict_litigation(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
