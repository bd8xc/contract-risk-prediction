"""Offline Kuzu export and Neo4j import. Runtime COI never imports Kuzu."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def export_kuzu(source: Path, destination: Path):
    import kuzu  # Install only in the legacy export environment.
    source = source.resolve(strict=True)
    if destination.exists():
        raise FileExistsError("Choose a new export filename; existing exports are preserved")
    if Path(str(source) + ".wal").exists():
        raise ValueError("Stop legacy writers and checkpoint the Kuzu database before export")
    # Read a private copy. Never open or reset the original database.
    with tempfile.TemporaryDirectory(prefix="coi-export-") as tmp:
        copy = Path(tmp) / "legacy"
        if source.is_dir():
            shutil.copytree(source, copy)
        else:
            shutil.copy2(source, copy)
        db = kuzu.Database(str(copy), read_only=True, buffer_pool_size=64 * 1024 * 1024, max_num_threads=2)
        conn = kuzu.Connection(db)
        def rows(query):
            result = conn.execute(query)
            names = result.get_column_names()
            values = []
            while result.has_next():
                values.append(dict(zip(names, result.get_next())))
            return values
        try:
            data = {
                "format": "coi-kuzu-export-v1",
                "entities": rows("MATCH (e:Entity) RETURN e.name AS name, e.label AS label, e.normalized_name AS normalized_name"),
                "sources": rows("MATCH (s:Source) RETURN s.doc_id AS doc_id, s.doc_type AS doc_type, s.filename AS filename"),
                "clauses": rows("MATCH (c:Clause) RETURN c.clause_id AS clause_id, c.text AS text"),
                "relationships": rows("MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) RETURN a.name AS source, b.name AS target, r.type AS type"),
                "contains": rows("MATCH (s:Source)-[:CONTAINS_CLAUSE]->(c:Clause) RETURN s.doc_id AS doc_id, c.clause_id AS clause_id"),
                "mentions": rows("MATCH (e:Entity)-[:EXTRACTED_FROM]->(c:Clause) RETURN e.name AS name, c.clause_id AS clause_id"),
            }
        finally:
            conn.close()
            db.close()
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {k: len(v) for k, v in data.items() if isinstance(v, list)}


def import_json(source: Path, *, graph=None):
    from .graph_manager import get_graph
    from .domain import ENTITY_RELATIONSHIPS
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("format") != "coi-kuzu-export-v1":
        raise ValueError("Unsupported export format")
    unknown = {r["type"] for r in data["relationships"]} - ENTITY_RELATIONSHIPS
    if unknown:
        raise ValueError(f"Review unsupported relationship types before import: {sorted(unknown)}")
    graph = graph or get_graph()
    graph.setup_schema()
    # Legacy edges have no per-edge source. Do not invent supporting clause references.
    # Preserve the complete legacy records in an immutable source snapshot.
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    entities = [{"name": e["name"], "label": e.get("label") or "Entity"} for e in data["entities"]]
    relations = [{"from": r["source"], "to": r["target"], "type": r["type"],
                  "verified": False, "evidence": "Legacy graph assertion; original edge provenance unavailable"}
                 for r in data["relationships"]]
    return graph.replace_document(
        {"id": "legacy-kuzu-" + digest, "type": "legacy_unverified", "filename": source.name},
        [{"clause_id": "legacy-snapshot", "text": source.read_text(encoding="utf-8"),
          "entities": entities, "relationships": relations}])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("database", type=Path)
    export.add_argument("output", type=Path)
    ingest = sub.add_parser("import")
    ingest.add_argument("export", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        print(export_kuzu(args.database, args.output))
    else:
        from .graph_manager import close_graph
        try:
            print(import_json(args.export))
        finally:
            close_graph()
