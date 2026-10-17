from io import BytesIO
from importlib import import_module

from docx import Document
from fastapi.testclient import TestClient

import coordinator
from app import app
from ingestion_pipeline.ldi.app.main import app as standalone_ldi


client = TestClient(app)


def test_frontend_pages_and_local_assets_are_served():
    pages = {
        "/": "Clarity for every contract",
        "/review": "New guided review",
        "/results": "Review report",
        "/workspaces": "Specialist workspaces",
        "/tools/conflicts": "Conflict of interest",
        "/tools/clauses": "Clause risk",
        "/tools/confidentiality": "Confidentiality leakage",
        "/tools/litigation": "Litigation exposure",
        "/advanced": "Test dashboard",
    }
    for path, title in pages.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert title in response.text, path
        assert "cdn.jsdelivr.net/npm/gsap" not in response.text, path

    for asset in ("styles.css", "atelier.css", "app.js", "atelier-motion.js", "advanced.css", "advanced.js"):
        assert client.get(f"/static/{asset}").status_code == 200, asset

    css = client.get("/static/styles.css", headers={"Accept-Encoding": "gzip"})
    assert css.headers["content-encoding"] == "gzip"


def test_one_openapi_schema_contains_agent_and_ingestion_routes():
    paths = app.openapi()["paths"]
    assert {
        "/api/analyze", "/api/coi/check", "/api/cr/analyze", "/api/cl/analyze",
        "/api/le/predict", "/api/risk/assess", "/api/ingestion/ingest/",
        "/api/ingestion/search/", "/api/ingestion/confidentiality/analyze",
    } <= paths.keys()
    assert "/ingest/" in standalone_ldi.openapi()["paths"]


def test_direct_cr_and_cl_routes_use_existing_agents(monkeypatch):
    seen = []

    def fake_cr(text):
        seen.append(text)
        return {"status": "complete", "clauses": [{"clause_id": "1", "model": {"prediction": "High"}}]}

    monkeypatch.setattr(coordinator, "_run_cr", fake_cr)
    cr = client.post("/api/cr/analyze", json={"contract_text": "An uncapped indemnity clause."})
    assert cr.status_code == 200
    assert cr.json()["clauses"][0]["model"]["prediction"] == "High"
    assert seen == ["An uncapped indemnity clause."]

    cl = client.post("/api/cl/analyze", json={
        "doc_id": "unified-api-test",
        "contract_text": "The contact is alex@example.com. Keep the record confidential.",
    })
    assert cl.status_code == 200
    assert cl.json()["status"] == "complete"
    assert any(item["type"] == "EMAIL" for item in cl.json()["findings"])
    assert all(item["value"] == "[redacted]" for item in cl.json()["findings"])


def test_shared_ingestion_router_accepts_docx():
    document = Document()
    document.add_paragraph("The parties agree to keep the test record confidential.")
    stream = BytesIO()
    document.save(stream)
    response = client.post("/api/ingestion/ingest/", files={
        "file": ("sample.docx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    })
    assert response.status_code == 200
    assert "test record confidential" in response.json()["text"]


def test_indexed_confidentiality_route_redacts_sensitive_values(monkeypatch):
    from agents.cl.confidentiality_leakage.agent import ConfidentialityLeakageAgent

    class IndexedClauses:
        def get_document_clauses(self, file_name):
            assert file_name == "synthetic-test.docx"
            return [{"clause_id": "1", "section": "Notices",
                     "text": "Send notices to qa-notices@example.org."}]

    indexed_router = import_module("agents.cl.confidentiality_leakage.router")
    monkeypatch.setattr(indexed_router, "_agent", ConfidentialityLeakageAgent(vector_store=IndexedClauses()))

    response = client.post("/api/ingestion/confidentiality/analyze",
                           json={"doc_id": "synthetic-test.docx"})

    assert response.status_code == 200
    findings = response.json()["findings"]
    assert any(finding["type"] == "EMAIL" for finding in findings)
    assert all(finding["value"] == "[redacted]" for finding in findings)
    assert "qa-notices@example.org" not in response.text


def test_indexed_search_rejects_invalid_query_and_result_count():
    assert client.post("/api/ingestion/search/", json={"query": "", "k": 5}).status_code == 422
    assert client.post("/api/ingestion/search/", json={"query": "confidentiality", "k": 0}).status_code == 422
