"""Use one COI response contract throughout the application."""
from typing import Any, TypedDict
from ...domain import ConflictReport

ConflictOutput = ConflictReport

class LexState(TypedDict, total=False):
    doc_id: str
    contract_text: str
    entities: dict[str, Any]
    graph_results: dict[str, Any]
    conflict_flag: int | None
    status: str
    litigation_probability: float | None
    clause_deviation_score: float | None
