"""LDI adapters use the same COI state and graph settings."""
from ...conflict_agent import ConflictOfInterestAgent, conflict_agent_node


def run_conflict_check(doc_id, client_entity, counterparty_entity,
                       contract_entities=None, additional_entities=None, *, agent=None):
    return (agent or ConflictOfInterestAgent()).run(doc_id=doc_id,
        client_entity=client_entity, counterparty_entity=counterparty_entity,
        contract_entities=contract_entities, additional_entities=additional_entities).to_lex_state_update()


def run_conflict_node(state, *, agent=None):
    return conflict_agent_node(state, agent=agent)
