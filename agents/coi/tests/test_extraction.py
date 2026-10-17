from types import SimpleNamespace
import pytest
from coi import extractor
from coi.domain import TRIGGERS, ENTITY_RELATIONSHIPS
from coi.ingester import chunk_by_clause, chunk_text_sliding_window


def test_all_triggers_are_extractable():
    assert set(TRIGGERS) <= ENTITY_RELATIONSHIPS


@pytest.mark.parametrize("kind", sorted(TRIGGERS))
def test_extraction_retains_triggers_and_evidence(monkeypatch, kind):
    monkeypatch.setattr(extractor, "_nlp", lambda: lambda text: SimpleNamespace(ents=[]))
    monkeypatch.setattr(extractor, "_generate", lambda *args: {
        "entities": [{"name": "A"}, {"name": "B"}],
        "relationships": [{"from": "A", "to": "B", "type": kind, "evidence": "A disputes B."}]})
    result = extractor.extract_from_text({"clause_id": "c", "text": "A disputes B."}, {}, {})
    assert result["relationships"][0]["type"] == kind
    assert result["relationships"][0]["verified"] is False


def test_invalid_evidence_stops_ingestion(monkeypatch):
    monkeypatch.setattr(extractor, "_nlp", lambda: lambda text: SimpleNamespace(ents=[]))
    monkeypatch.setattr(extractor, "_generate", lambda *args: {
        "entities": [{"name": "A"}, {"name": "B"}],
        "relationships": [{"from": "A", "to": "B", "type": "DISPUTE_WITH", "evidence": "invented"}]})
    with pytest.raises(extractor.ExtractionError):
        extractor.extract_from_text({"text": "A disputes B."}, {}, {})


def test_short_content_is_retained():
    text = "Preamble obligation.\n1. ALL LIABILITY IS UNLIMITED\n2. Pay now."
    chunks = chunk_by_clause(text)
    assert "Preamble obligation." in chunks
    assert any("ALL LIABILITY" in c for c in chunks)
    with pytest.raises(ValueError):
        chunk_text_sliding_window(text, 50, 50)


def test_pdf_pipeline_propagates_ingestion_failure(monkeypatch):
    from coi.ldi import pipeline
    class Graph:
        def setup_schema(self):
            pass
    def fail(*args, **kwargs):
        raise extractor.ExtractionError("no evidence")
    monkeypatch.setattr(pipeline, "process_pdf", fail)
    with pytest.raises(extractor.ExtractionError):
        pipeline.analyze_pdf("unused.pdf", doc_id="D", client_entity="A", counterparty_entity="B", graph=Graph())
