"""The indexed routes must never mix clauses from different uploads."""

import numpy as np

from ingestion_pipeline.ldi.embeddings import pipeline
from ingestion_pipeline.ldi.embeddings.vector_store import ClauseVectorStore


def test_replacing_document_removes_old_clauses_and_preserves_other_files(monkeypatch, tmp_path):
    class LocalStore(ClauseVectorStore):
        def __init__(self):
            super().__init__(persist_directory=str(tmp_path))

    class FakeEmbedder:
        def embed(self, texts):
            return np.asarray([[float(len(text)), 1.0] for text in texts])

    monkeypatch.setattr(pipeline, "ClauseVectorStore", LocalStore)
    monkeypatch.setattr(pipeline, "ClauseEmbedder", FakeEmbedder)

    original = [
        {"clause_id": "1", "section": "Notices", "level": "clause", "text": "Old notice address."},
        {"clause_id": "2", "section": "Term", "level": "clause", "text": "Old renewal term."},
    ]
    revised = [
        {"clause_id": "1", "section": "Notices", "level": "clause", "text": "New notice address."},
    ]

    assert pipeline.embed_and_store(original, "contract.docx")["clauses"] == 2
    assert pipeline.embed_and_store(original, "other.docx")["clauses"] == 2
    assert pipeline.embed_and_store(original, "contract.docx")["cached"] is True
    assert pipeline.embed_and_store(revised, "contract.docx")["clauses"] == 1

    store = LocalStore()
    assert [row["text"] for row in store.get_document_clauses("contract.docx")] == ["New notice address."]
    assert {row["text"] for row in store.get_document_clauses("other.docx")} == {
        "Old notice address.", "Old renewal term.",
    }
    assert len(store._collection.get(where={"file_name": "contract.docx"})["ids"]) == 1
