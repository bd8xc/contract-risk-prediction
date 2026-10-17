"""Optional LE handoff. COI can run without the separate LE package."""
from importlib import import_module
import os
from .conflict_agent import ConflictOfInterestAgent


def predict_litigation(*, entities, graph_results, clause_deviation_score, litigation_agent=None):
    if graph_results.get("status", "complete") != "complete" or (type(graph_results.get("conflict_flag")) is not int or graph_results["conflict_flag"] not in (0, 1)):
        raise ValueError("LE requires a complete COI result with a known conflict flag")
    if litigation_agent is None:
        name = os.getenv("LE_MODULE", "le")
        try:
            module = import_module(name)
        except ImportError as exc:
            raise RuntimeError("LE package is unavailable; install it and set LE_MODULE") from exc
        litigation_agent = module.LitigationExposureAgent()
        state = module.LexState(entities=entities, graph_results=graph_results,
                                clause_deviation_score=clause_deviation_score)
    else:
        state = {"entities": entities, "graph_results": graph_results,
                 "clause_deviation_score": clause_deviation_score}
    return litigation_agent.predict_with_explanation(state)


def assess_litigation_after_coi(*, doc_id, client_entity, counterparty_entity,
        litigation_entities, clause_deviation_score, contract_entities=None,
        additional_entities=None, coi_agent=None, litigation_agent=None):
    report = (coi_agent or ConflictOfInterestAgent()).run(
        doc_id=doc_id, client_entity=client_entity, counterparty_entity=counterparty_entity,
        contract_entities=contract_entities, additional_entities=additional_entities)
    if report.status != "complete":
        return {"coi": report.to_dict(), "litigation": None, "status": "incomplete"}
    prediction = predict_litigation(entities=litigation_entities,
        graph_results=report.to_dict(), clause_deviation_score=clause_deviation_score,
        litigation_agent=litigation_agent)
    return {"coi": report.to_dict(), "litigation": prediction, "status": "complete"}
