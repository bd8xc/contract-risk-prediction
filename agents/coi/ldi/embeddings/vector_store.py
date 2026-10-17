"""
ClauseVectorStore: Handles persistent storage and retrieval of clause embeddings using ChromaDB.
"""
from typing import List, Dict, Any
import numpy as np
import chromadb
from chromadb.config import Settings

class ClauseVectorStore:
    """
    Stores and retrieves clause embeddings and metadata in a persistent ChromaDB collection.
    """
    def __init__(self, persist_directory: str = "./chroma", collection_name: str = "clauses"):
        self._client = chromadb.PersistentClient(path=persist_directory, settings=Settings(allow_reset=True))
        self._collection = self._client.get_or_create_collection(collection_name)

    def add(self, ids: List[str], texts: List[str], embeddings: np.ndarray, metadatas: List[Dict[str, Any]]):
        """
        Add embeddings and metadata to the vector store.
        Args:
            ids (List[str]): Unique IDs for each clause.
            texts (List[str]): Clause texts.
            embeddings (np.ndarray): Embeddings array.
            metadatas (List[Dict[str, Any]]): Metadata dicts for each clause.
        """
        if not ids or len(ids) != len(texts) or len(ids) != len(embeddings) or len(ids) != len(metadatas):
            raise ValueError("Input lists must be non-empty and of equal length.")
        # Use upsert so re-indexing the same IDs updates rows instead of failing.
        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas
        )

    def search(self, query_embedding: np.ndarray, k: int = 5):
        """
        Search for the top-k most similar clauses to the query embedding.
        Args:
            query_embedding (np.ndarray): Query embedding vector.
            k (int): Number of results to return.
        Returns:
            List[Dict]: List of matching clause metadata and scores.
        """
        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k
        )
        return results
