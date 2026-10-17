"""Real Neo4j tests. Set COI_TEST_NEO4J=1 for an isolated test server."""
import os
from uuid import uuid4
import pytest
from coi.graph_manager import LexGraph
from coi.conflict_agent import ConflictOfInterestAgent

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("COI_TEST_NEO4J") != "1", reason="Set COI_TEST_NEO4J=1 with a disposable Neo4j server")]


@pytest.fixture
def graph():
    with LexGraph() as g:
        g.setup_schema()
        yield g


def test_roundtrip_replacement_provenance_and_resolution(graph):
    uid = uuid4().hex
    doc_id = "test-" + uid
    a, b = "A-" + uid, "B-" + uid
    clause = {"clause_id": "c1", "text": 'Original "quoted" evidence.',
              "entities": [{"name": a}, {"name": b}],
              "relationships": [{"from": a, "to": b, "type": "LITIGATING_AGAINST",
                                  "evidence": 'Original "quoted" evidence.', "verified": True}]}
    try:
        graph.replace_document({"id": doc_id}, [clause])
        agent = ConflictOfInterestAgent(graph=graph)
        result = agent.run(doc_id="input", client_entity=a.upper(), counterparty_entity=b)
        assert result.severity == "HIGH"
        assert result.findings[0]["evidence"][0]["evidence"] == clause["text"]
        assert result.findings[0]["evidence"][0]["doc_id"] == doc_id
        clause["relationships"] = []
        graph.replace_document({"id": doc_id}, [clause])
        assert agent.run(doc_id="input", client_entity=a, counterparty_entity=b).severity == "NONE"
        clause["relationships"] = [{"from": a, "to": b, "type": "INVALID"}]
        with pytest.raises(ValueError):
            graph.replace_document({"id": doc_id}, [clause])
        assert agent.run(doc_id="input", client_entity=a, counterparty_entity=b).status == "complete"
    finally:
        with graph.driver.session(database=graph.database) as session:
            session.run("MATCH (n:COIEntity) WHERE n.key IN $keys DETACH DELETE n", keys=[a.lower(), b.lower()]).consume()
            session.run("MATCH (s:COISource {doc_id:$id})-[:CONTAINS_CLAUSE]->(c) DETACH DELETE c", id=doc_id).consume()
            session.run("MATCH (s:COISource {doc_id:$id}) DETACH DELETE s", id=doc_id).consume()


def test_expired_relationship_is_not_current(graph):
    uid = uuid4().hex
    a, b, doc_id = "A-" + uid, "B-" + uid, "dated-" + uid
    try:
        graph.replace_document({"id": doc_id}, [{"clause_id": "c", "text": "Historical dispute",
            "entities": [{"name": a}, {"name": b}], "relationships": [
                {"from": a, "to": b, "type": "DISPUTE_WITH", "valid_until": "2020-01-01"}]}])
        agent = ConflictOfInterestAgent(graph=graph)
        assert agent.run(doc_id="input", client_entity=a, counterparty_entity=b, as_of="2019-01-01").conflict_detected
        assert not agent.run(doc_id="input", client_entity=a, counterparty_entity=b, as_of="2026-01-01").conflict_detected
    finally:
        with graph.driver.session(database=graph.database) as session:
            session.run("MATCH (n:COIEntity) WHERE n.key IN $keys DETACH DELETE n", keys=[a.lower(), b.lower()]).consume()
            session.run("MATCH (s:COISource {doc_id:$id})-[:CONTAINS_CLAUSE]->(c) DETACH DELETE c", id=doc_id).consume()
            session.run("MATCH (s:COISource {doc_id:$id}) DETACH DELETE s", id=doc_id).consume()


def test_transaction_rollback_and_shared_driver(graph):
    from concurrent.futures import ThreadPoolExecutor
    uid = uuid4().hex
    a, b, doc_id = "A-" + uid, "B-" + uid, "rollback-" + uid
    clause = {"clause_id": "c", "text": "fact", "entities": [{"name": a}, {"name": b}],
              "relationships": [{"from": a, "to": b, "type": "COMPETES_WITH"}]}
    try:
        graph.replace_document({"id": doc_id}, [clause])
        # Force failure inside a real transaction, after deleting the old relationships.
        real_driver = graph.driver
        class BrokenTx:
            def __init__(self, tx):
                self.tx = tx
            def run(self, query, **params):
                if "CREATE (c:COIClause" in query:
                    raise RuntimeError("simulated write failure")
                return self.tx.run(query, **params)
        class Session:
            def __enter__(self):
                self.session = real_driver.session(database=graph.database)
                return self
            def __exit__(self, *args):
                self.session.close()
            def execute_write(self, callback):
                return self.session.execute_write(lambda tx: callback(BrokenTx(tx)))
        class Driver:
            def session(self, **kwargs):
                return Session()
        broken = LexGraph(driver=Driver(), database=graph.database)
        with pytest.raises(RuntimeError, match="simulated"):
            broken.replace_document({"id": doc_id}, [clause])
        agent = ConflictOfInterestAgent(graph=graph)
        def check(_):
            return agent.run(doc_id="request", client_entity=a, counterparty_entity=b).severity
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(check, range(4))) == ["MEDIUM"] * 4
    finally:
        with graph.driver.session(database=graph.database) as session:
            session.run("MATCH (n:COIEntity) WHERE n.key IN $keys DETACH DELETE n", keys=[a.lower(), b.lower()]).consume()
            session.run("MATCH (s:COISource {doc_id:$id})-[:CONTAINS_CLAUSE]->(c) DETACH DELETE c", id=doc_id).consume()
            session.run("MATCH (s:COISource {doc_id:$id}) DETACH DELETE s", id=doc_id).consume()
