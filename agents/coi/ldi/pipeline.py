"""One call for PDF ingestion and COI assessment."""
from ..ingester import process_pdf
from ..conflict_agent import ConflictOfInterestAgent
from ..graph_manager import get_graph


def analyze_pdf(file_path, *, doc_id, client_entity, counterparty_entity,
                doc_type="Contract", additional_entities=None, graph=None):
    graph = graph or get_graph()
    graph.setup_schema()
    ingestion = process_pdf(file_path, doc_id, doc_type, graph=graph)
    report = ConflictOfInterestAgent(graph=graph).run(
        doc_id=doc_id, client_entity=client_entity, counterparty_entity=counterparty_entity,
        additional_entities=additional_entities)
    return {"ingestion": ingestion, **report.to_lex_state_update()}
