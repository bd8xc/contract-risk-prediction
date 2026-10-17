from fastapi.testclient import TestClient
from coi.api.main import app
from coi.api import routes
from coi.conflict_agent import ConflictOfInterestAgent
from coi.tests.test_conflict_agent import FakeGraph


def test_api_loads_without_le_and_serializes_unknown(monkeypatch):
    monkeypatch.setattr(routes, "get_agent", lambda: ConflictOfInterestAgent(graph=FakeGraph()))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.post("/coi/check", json={"doc_id": "D", "client_entity": "A", "counterparty_entity": "B"})
        assert response.status_code == 200
        assert response.json()["conflict_flag"] is None
        assert response.json()["status"] == "unknown"


def test_api_returns_evidence(monkeypatch):
    graph = FakeGraph([("A", "B", "LITIGATING_AGAINST")])
    monkeypatch.setattr(routes, "get_agent", lambda: ConflictOfInterestAgent(graph=graph))
    with TestClient(app) as client:
        response = client.post("/coi/check", json={"doc_id": "D", "client_entity": "A", "counterparty_entity": "B"})
        assert response.json()["severity"] == "HIGH"
        assert response.json()["findings"][0]["evidence"][0]["doc_id"] == "source"
        assert client.post("/coi/check", json={"doc_id": "D", "client_entity": " ", "counterparty_entity": "B"}).status_code == 400


def test_le_rejects_unknown_flag():
    from coi.le_integration import predict_litigation
    import pytest
    with pytest.raises(ValueError):
        predict_litigation(entities={}, graph_results={"conflict_flag": None}, clause_deviation_score=0.2)


def test_handoff_skips_le_for_unknown():
    from coi.le_integration import assess_litigation_after_coi
    class Forbidden:
        def predict_with_explanation(self, state):
            raise AssertionError("LE must not run")
    result = assess_litigation_after_coi(doc_id="D", client_entity="A", counterparty_entity="B",
        litigation_entities={}, clause_deviation_score=0.1,
        coi_agent=ConflictOfInterestAgent(graph=FakeGraph()), litigation_agent=Forbidden())
    assert result["status"] == "incomplete" and result["litigation"] is None
