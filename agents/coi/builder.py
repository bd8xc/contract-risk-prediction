"""Small graph ingestion interface. Errors propagate to the caller."""
from .graph_manager import get_graph


def ingest_document(doc_meta, clauses, *, graph=None):
    return (graph or get_graph()).replace_document(doc_meta, clauses)


def ingest_document_data(doc_meta, chunk_meta, entities, relationships, *, graph=None):
    """Replace a single-clause document. Use ingest_document for multiple clauses."""
    return ingest_document(doc_meta, [{**chunk_meta, "entities": entities,
                                     "relationships": relationships}], graph=graph)
