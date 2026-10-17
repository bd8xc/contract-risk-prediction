"""PDF ingestion with atomic document replacement and explicit failures."""
from pathlib import Path
import re
from .builder import ingest_document
from .extractor import extract_from_text, generate_alias_map


def clean_text(text):
    # Keep legal content, including URLs, dates, and short obligations.
    return text.strip()


def chunk_text_sliding_window(text, words_per_chunk=300, overlap=50):
    if words_per_chunk <= 0 or not 0 <= overlap < words_per_chunk:
        raise ValueError("Require 0 <= overlap < words_per_chunk")
    words = text.split()
    return [" ".join(words[i:i + words_per_chunk])
            for i in range(0, len(words), words_per_chunk - overlap)]


def chunk_by_clause(text):
    blocks = re.split(r"(?m)(?=^\s*(?:(?:ARTICLE|SECTION|CLAUSE)\s+[0-9IVX]+|\d+(?:\.\d+)*\.?\s+))", text)
    return [b.strip() for b in blocks if b.strip()]


def process_pdf(file_path, doc_id, doc_type, *, graph=None):
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF requires decryption before ingestion")
    pages = [p.extract_text() or "" for p in reader.pages]
    if not pages or any(not text.strip() for text in pages):
        raise ValueError("PDF contains unreadable pages; provide OCR text before ingestion")
    doc = {"id": doc_id, "type": doc_type, "filename": Path(file_path).name}
    text = "\n\n".join(pages)
    chunks = chunk_by_clause(text)
    aliases = generate_alias_map(chunks[0])
    clauses = [extract_from_text({"clause_id": f"{doc_id}_CLAUSE_{i}", "text": chunk}, doc, aliases)
               for i, chunk in enumerate(chunks, 1)]
    return ingest_document(doc, clauses, graph=graph)


if __name__ == "__main__":
    import argparse
    from .graph_manager import close_graph
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--doc-type", default="Contract")
    args = parser.parse_args()
    try:
        print(process_pdf(args.pdf, args.doc_id, args.doc_type))
    finally:
        close_graph()
