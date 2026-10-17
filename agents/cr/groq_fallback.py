"""Groq-only CR mode used until a trained LegalBERT checkpoint is available."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from llm.local_llm import GroqLegalLLM
from rag.corpus import load_legal_sections


CR_ROOT = Path(__file__).resolve().parent
LEGAL_CORPUS = CR_ROOT / "knowledge_base" / "processed" / "indian_contract_act_sections.json"


class GroqFallbackAnalyzer:
    """Use the shared Groq legal reasoner with local TF-IDF law retrieval.

    This mode does not emulate LegalBERT. Its output is explicitly marked as
    preliminary and must not be treated as a trained classifier result.
    """

    def __init__(self) -> None:
        self.sections, self.excluded_sections = load_legal_sections(LEGAL_CORPUS)
        self.source_warning = (
            "Legal text extraction has not been independently reviewed; "
            f"excluded {len(self.excluded_sections)} suspect section(s)."
        )
        self.documents = [
            f"Section {s.get('section', '')}. {s.get('heading', '')}. {s.get('text', '')}"
            for s in self.sections
        ]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=30000)
        self.matrix = self.vectorizer.fit_transform(self.documents)
        self.llm = GroqLegalLLM()
        if not self.llm.check_connection():
            raise RuntimeError("Groq is unavailable; check GROQ_API_KEY and GROQ_MODEL")

    def _retrieve(self, clause: str, top_k: int = 5) -> list[dict]:
        query = self.vectorizer.transform([clause])
        scores = (self.matrix @ query.T).toarray().ravel()
        indices = np.argsort(scores)[::-1]
        results = []
        for index in indices:
            if scores[index] <= 0 or len(results) >= top_k:
                break
            section = self.sections[int(index)]
            results.append({
                "section": str(section.get("section", "Unknown")),
                "heading": str(section.get("heading", "")),
                "text": str(section.get("text", "")),
                "score": float(scores[index]),
                "extraction_verified": False,
            })
        return results

    def analyze(self, clause: str) -> dict:
        retrieved_law = self._retrieve(clause)
        analysis = self.llm.analyze(
            clause=clause,
            model_result=None,
            retrieved_law=retrieved_law,
        )
        risk = str(analysis.get("assessed_risk", "Unknown")).strip().title()
        if risk not in {"Low", "Medium", "High"}:
            risk = "Unknown"
        return {
            "model": {"prediction": risk, "model_source": "Groq only; LegalBERT checkpoint missing"},
            "analysis": analysis,
            "retrieved_law": retrieved_law,
        }
