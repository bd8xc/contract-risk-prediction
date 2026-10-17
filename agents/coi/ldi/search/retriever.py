"""
ClauseRetriever: Semantic search over embedded legal clauses in ChromaDB.
"""
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

class ClauseRetriever:
    """
    Retrieves most similar legal clauses or tables to a query using embeddings and ChromaDB.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", persist_directory: str = "./chroma", collection_name: str = "clauses"):
        self._model = SentenceTransformer(model_name)
        self._client = chromadb.PersistentClient(path=persist_directory, settings=Settings(allow_reset=True))
        self._collection = self._client.get_or_create_collection(collection_name)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for the top-k most similar clauses or tables to the query string.
        Args:
            query (str): Query text.
            k (int): Number of results to return.
        Returns:
            List[Dict]: List of matching clause/table dicts with metadata and score.
        """
        if not query:
            return []

        # Empty DB guard
        try:
            if self._collection.count() == 0:
                return []
        except Exception:
            # If count() isn't available for any reason, just proceed.
            pass

        query_emb = self._model.encode([query], show_progress_bar=False, convert_to_numpy=True)[0]

        results = None
        try:
            if self._should_prioritize_tables(query):
                results = self._collection.query(
                    query_embeddings=[query_emb.tolist()],
                    n_results=k,
                    where={"level": "table"},
                )
                # If no table matches, fall back to full-corpus search.
                if not results.get("ids") or not results.get("ids", [[]])[0]:
                    results = None

            if results is None:
                results = self._collection.query(
                    query_embeddings=[query_emb.tolist()],
                    n_results=k,
                )
        except Exception:
            return []
        matches = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        scores = results.get("distances", [[]])[0] if "distances" in results else [None]*len(ids)
        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else {}
            text = documents[i] if i < len(documents) else None
            # Use formatting for table chunks everywhere
            if meta.get("level") == "table" and text:
                text = self._format_table_text(text)
            match = {
                "clause_id": meta.get("clause_id"),
                "section": meta.get("section"),
                "level": meta.get("level"),
                "file_name": meta.get("file_name"),
                "text": text,
                "score": float(scores[i]) if scores and i < len(scores) and scores[i] is not None else None
            }
            matches.append(match)
        return matches

    def _should_prioritize_tables(self, query: str) -> bool:
        """Heuristic: if the user asks for a table, search table chunks first."""
        q = query.lower()
        return "table" in q or "tabular" in q or "rows" in q or "columns" in q

    def _format_table_text(self, table_text: str) -> str:
        """
        Formats table chunk text for display (tabular view).
        """
        lines = table_text.split("\n")
        formatted = "\n".join([" | ".join(row.split("\t")) for row in lines])
        return formatted
