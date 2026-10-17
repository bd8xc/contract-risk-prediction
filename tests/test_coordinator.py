from pathlib import Path

import coordinator


def test_cl_scans_short_preamble_before_numbered_clauses():
    text = "a@b.co\n\n1. TERMS\n\n1.1 The parties agree to the terms of this contract."

    report = coordinator._run_cl(text, "coverage-test")

    assert any(finding["type"] == "EMAIL" and finding["clause_id"] == "P1"
               for finding in report["findings"])
    assert all(finding["value"] == "[redacted]" for finding in report["findings"])


def test_cr_reports_omitted_clauses_and_keeps_working_directory(monkeypatch, tmp_path):
    original_directory = Path.cwd()
    checkpoint = tmp_path / "best_model.pt"
    checkpoint.touch()
    monkeypatch.setattr(coordinator, "CR_CHECKPOINT", checkpoint)

    class FakePredictor:
        def predict(self, clause):
            assert Path.cwd() == original_directory
            return {"prediction": "Low"}

    monkeypatch.setattr(coordinator, "_cr_predictor", FakePredictor())
    text = "\n".join(
        f"{index}.1 This agreement contains enough words for clause risk analysis."
        for index in range(1, 14)
    )

    result = coordinator._run_cr(text)

    assert result["status"] == "incomplete"
    assert result["omitted_clause_count"] == 1
    assert len(result["clauses"]) == 12
    assert Path.cwd() == original_directory


def test_cr_unknown_clause_is_incomplete(monkeypatch, tmp_path):
    checkpoint = tmp_path / "best_model.pt"
    checkpoint.touch()
    monkeypatch.setattr(coordinator, "CR_CHECKPOINT", checkpoint)

    class FakePredictor:
        def predict(self, clause):
            risk = "Low" if "first" in clause else "Unknown"
            return {"prediction": risk}

    monkeypatch.setattr(coordinator, "_cr_predictor", FakePredictor())
    result = coordinator._run_cr(
        "1.1 The first clause can be assessed.\n1.2 The second clause cannot be assessed.")

    assert result["status"] == "incomplete"
    assert "1 clause" in result["reason"]


def test_le_requires_measured_deviation_not_cr_risk_label(monkeypatch):
    from coi.domain import ConflictReport

    request = coordinator.AnalyzeRequest(
        client_entity="A", counterparty_entity="B",
        contract_text="The parties agree to confidentiality and a thirty day notice period.",
        features=coordinator.ContractFeatures(
            deal_size=750000, liability_cap=1, auto_renewal=0,
            jurisdiction_risk=5, indemnification_clause=1,
            dispute_history=0, governing_law_clarity=3),
    )
    monkeypatch.setattr(coordinator, "_run_coi", lambda *_: ConflictReport(severity="NONE", review_required=False))
    monkeypatch.setattr(coordinator, "_run_cr", lambda *_: {
        "status": "complete", "mode": "legalbert",
        "clauses": [{"model": {"prediction": "High"}}]})
    monkeypatch.setattr(coordinator, "_run_cl", lambda *_: {"findings": []})

    def run_le(*args):
        assert args[2] == 0.4
        return {"litigation_probability": 0.5}

    monkeypatch.setattr(coordinator, "_run_le", run_le)
    without_measurement = coordinator.analyze(request)
    assert without_measurement["le"] is None
    assert without_measurement["clause_deviation_score"] is None

    request.clause_deviation_override = 0.4
    with_measurement = coordinator.analyze(request)
    assert with_measurement["le"]["litigation_probability"] == 0.5
    assert with_measurement["clause_deviation_source"] == "manual_template_measurement"


def test_cr_keeps_preamble_and_short_numbered_clause():
    clauses, omitted = coordinator._cr_clauses(
        "The receiving party shall keep the attached schedule confidential.\n"
        "1. TERMS\n"
        "1.1 No disclosure.\n"
        "1.2 Both parties shall return records upon termination."
    )

    assert omitted == 0
    assert [clause["id"] for clause in clauses] == ["P0", "1.1", "1.2"]
    assert clauses[1]["text"] == "No disclosure."


def test_cr_paths_are_independent_of_working_directory():
    from models.config import Config
    from rag.knowledge_loader import LegalKnowledgeLoader
    from rag.legal_rag import IndianLegalRAG

    assert Config().checkpoint_path == coordinator.CR_CHECKPOINT
    assert LegalKnowledgeLoader().knowledge_path.is_file()
    assert Path(IndianLegalRAG.DEFAULT_SOURCE_PATH).is_file()


def test_cr_failed_clause_is_not_reported_as_complete(monkeypatch, tmp_path):
    checkpoint = tmp_path / "best_model.pt"
    checkpoint.touch()
    monkeypatch.setattr(coordinator, "CR_CHECKPOINT", checkpoint)

    class FakePredictor:
        def predict(self, clause):
            if "second" in clause:
                raise RuntimeError("analysis failed")
            return {"prediction": "Low"}

    monkeypatch.setattr(coordinator, "_cr_predictor", FakePredictor())
    text = (
        "1.1 The first clause contains enough contract wording to be analyzed.\n"
        "1.2 The second clause contains enough contract wording to be analyzed."
    )

    result = coordinator._run_cr(text)

    assert result["status"] == "incomplete"
    assert len(result["clauses"]) == 2
    assert result["clauses"][1]["status"] == "error"


def test_cr_uses_legalbert_without_llm_and_keeps_seed_distinct(monkeypatch, tmp_path):
    checkpoint = tmp_path / "best_model.pt"
    checkpoint.touch()
    monkeypatch.setattr(coordinator, "CR_CHECKPOINT", checkpoint)

    class FakePredictor:
        def predict(self, clause):
            return {"prediction": "Seed" if "Preamble" in clause else "High", "model_score": 0.8}

    monkeypatch.setattr(coordinator, "_cr_predictor", FakePredictor())
    result = coordinator._run_cr("Preamble for the agreement.\n1.1 Supplier indemnifies the buyer for all losses.")

    assert result["status"] == "complete"
    assert result["mode"] == "legalbert"
    assert [clause["model"]["prediction"] for clause in result["clauses"]] == ["Seed", "High"]
    assert all("analysis" not in clause and "retrieved_law" not in clause for clause in result["clauses"])


def test_cr_does_not_substitute_groq_when_checkpoint_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(coordinator, "CR_CHECKPOINT", tmp_path / "absent.pt")
    result = coordinator._run_cr("1.1 Supplier shall perform the services.")
    assert result["status"] == "unavailable"
    assert result["clauses"] == []


def test_retriever_initializes_reranker_when_requested(monkeypatch):
    import rag.retriever as module

    class FakeReranker:
        def rerank(self, *, query, candidates, top_k):
            return [{"query": query, "candidates": candidates, "top_k": top_k}]

    monkeypatch.setattr(module, "LegalPrincipleReranker", FakeReranker)
    retriever = module.LegalPrincipleRetriever.__new__(module.LegalPrincipleRetriever)
    retriever.principles = [{}]
    retriever.reranker = None
    retriever.retrieve = lambda *, query, top_k: [{"rank": 1, "query": query}]

    result = retriever.retrieve_and_rerank("limitation of liability")

    assert result[0]["top_k"] == 1
    assert result[0]["candidates"][0]["query"] == "limitation of liability"
