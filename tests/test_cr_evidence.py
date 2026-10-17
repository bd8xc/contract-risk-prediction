"""CR must reject malformed explanations and misparsed legal sections."""
import json

import pytest

from groq_fallback import LEGAL_CORPUS
from llm import local_llm
from rag.corpus import load_legal_sections


def test_legal_retrieval_excludes_known_editorial_rows():
    sections, excluded = load_legal_sections(LEGAL_CORPUS)

    assert {"1", "2", "3", "4"} <= set(excluded)
    assert "5" in {row["section"] for row in sections}
    assert not {"1", "2", "3", "4"} & {row["section"] for row in sections}


@pytest.mark.parametrize("mutation", [
    {"evidence_sufficient": "false"},
    {"relevant_sections": [{"section": "999999", "relevance": "Invented citation"}]},
    [],
])
def test_groq_rejects_invalid_or_invented_evidence(monkeypatch, mutation):
    valid = {
        "assessed_risk": "Low",
        "agreement_with_model": False,
        "summary": "A preliminary assessment.",
        "risk_reasoning": "The clause has a defined notice period.",
        "relevant_sections": [{"section": "5", "relevance": "Relevant context"}],
        "irrelevant_or_weak_sections": [],
        "contractual_concern": "Notice period",
        "suggested_mitigation": "Review notice terms.",
        "human_review_required": True,
        "evidence_sufficient": True,
    }
    response = valid | mutation if isinstance(mutation, dict) else mutation
    monkeypatch.setattr(local_llm, "groq_chat_completion", lambda *args, **kwargs: json.dumps(response))

    result = local_llm.GroqLegalLLM().analyze(
        "The agreement can be terminated on thirty days notice.",
        model_result=None,
        retrieved_law=[{"section": "5", "text": "A proposal may be revoked."}],
    )

    assert result["assessed_risk"] == "Unknown"
    assert result["human_review_required"] is True
    assert result["evidence_sufficient"] is False


def test_groq_cannot_claim_sufficient_law_without_relevant_citation(monkeypatch):
    response = {
        "assessed_risk": "Medium", "agreement_with_model": True,
        "summary": "Review", "risk_reasoning": "Review", "relevant_sections": [],
        "irrelevant_or_weak_sections": [], "contractual_concern": "Review",
        "suggested_mitigation": "Review", "human_review_required": False,
        "evidence_sufficient": True,
    }
    monkeypatch.setattr(local_llm, "groq_chat_completion", lambda *args, **kwargs: json.dumps(response))

    result = local_llm.GroqLegalLLM().analyze("The parties agree to review.", None, [])

    assert result["assessed_risk"] == "Medium"
    assert result["agreement_with_model"] is False
    assert result["evidence_sufficient"] is False
    assert result["human_review_required"] is True
