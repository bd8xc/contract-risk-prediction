from fastapi import FastAPI, UploadFile, File, Body
from typing import List
import shutil
import os
from ldi.search.pipeline import search_clauses
from pydantic import BaseModel
from agents.confidentiality_leakage.router import router as confidentiality_router

# PDF loader: extracts both text and tables from PDF
from ldi.ingestion.pdf_table_loader import extract_pdf_text_and_tables
# DOCX loader: extracts both text and tables from DOCX
from ldi.ingestion.docx_loader import load_docx
# Clause chunker: splits text into legal clause objects
from ldi.chunking.clause_splitter import split_clauses

# Embedding pipeline
from ldi.embeddings.pipeline import embed_and_store
# Search pipeline
from ldi.search.pipeline import search_clauses
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    k: int = 5

# Initialize FastAPI app

app = FastAPI()
app.include_router(confidentiality_router)


# ==============================
# EMBED ENDPOINT: Embeds and stores legal clauses from uploaded PDF or DOCX
# ==============================
from fastapi import HTTPException


# @app.post("/embed/")
# async def embed_document(file: UploadFile = File(...)):
#     """
#     Extracts, chunks, embeds, and stores legal clauses from a document.
#     Returns number of clauses indexed and status.
#     """
#     temp_path = f"temp_{file.filename}"
#     with open(temp_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
#     try:
#         if file.filename.lower().endswith(".pdf"):
#             result = extract_pdf_text_and_tables(temp_path)
#         elif file.filename.lower().endswith(".docx"):
#             result = load_docx(temp_path)
#         else:
#             raise HTTPException(status_code=400, detail="Unsupported file type")
#         text = result["text"]
#         clauses = split_clauses(text)
#
#         # Also index extracted tables as single chunks (one chunk per table).
#         for table_index, table in enumerate(result.get("tables", []) or [], start=1):
#             table_text = "\n".join(["\t".join(row) for row in table])
#             clauses.append(
#                 {
#                     "clause_id": f"TABLE_{table_index}",
#                     "section": f"Table {table_index}",
#                     "level": "table",
#                     "text": table_text,
#                 }
#             )
#         stats = embed_and_store(clauses, file.filename)
#     finally:
#         os.remove(temp_path)
#     return {"clauses_indexed": stats["clauses"], "status": "success"}




# ==============================
# INGEST ENDPOINT: Extracts text and tables from uploaded PDF or DOCX (single file)
# ==============================
@app.post("/ingest/")
async def ingest_document(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        if file.filename.lower().endswith(".pdf"):
            result = extract_pdf_text_and_tables(temp_path)
        elif file.filename.lower().endswith(".docx"):
            result = load_docx(temp_path)
        else:
            return {"error": "Unsupported file type"}
    finally:
        os.remove(temp_path)
    return result


# ==============================
# CHUNK ENDPOINT: Splits text into legal clauses and returns tables (single file)
# ==============================
@app.post("/chunk/")
async def chunk_document(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        if file.filename.lower().endswith(".pdf"):
            result = extract_pdf_text_and_tables(temp_path)
        elif file.filename.lower().endswith(".docx"):
            result = load_docx(temp_path)
        else:
            return {"error": "Unsupported file type"}
        text = result["text"]
        tables = result["tables"]
        clauses = split_clauses(text)
    finally:
        os.remove(temp_path)
    return {
        "clauses": clauses,
        "tables": tables,
        "clause_count": len(clauses),
        "table_count": len(tables)
    }


# ==============================
# INGEST MULTI ENDPOINT: Extracts text and tables from multiple uploaded PDFs or DOCXs
# ==============================
@app.post("/ingest-multi/")
async def ingest_documents(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            if file.filename.lower().endswith(".pdf"):
                result = extract_pdf_text_and_tables(temp_path)
            elif file.filename.lower().endswith(".docx"):
                result = load_docx(temp_path)
            else:
                result = {"error": f"Unsupported file type: {file.filename}"}
        finally:
            os.remove(temp_path)
        results.append({"filename": file.filename, **result})
    return results



# ==============================
# CHUNK MULTI ENDPOINT: Splits text into legal clauses and returns tables (multiple files)
# ==============================
@app.post("/chunk-multi/")
async def chunk_documents(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            if file.filename.lower().endswith(".pdf"):
                result = extract_pdf_text_and_tables(temp_path)
            elif file.filename.lower().endswith(".docx"):
                result = load_docx(temp_path)
            else:
                results.append({"filename": file.filename, "error": "Unsupported file type"})
                continue
            text = result["text"]
            tables = result["tables"]
            clauses = split_clauses(text)
            results.append({
                "filename": file.filename,
                "clauses": clauses,
                "tables": tables,
                "clause_count": len(clauses),
                "table_count": len(tables)
            })
        finally:
            os.remove(temp_path)
    return results


@app.post("/embed-multi/")
async def embed_documents(files: List[UploadFile] = File(...)):
    """
    Embeds and stores legal clauses from multiple uploaded PDF or DOCX files.
    Returns a list of results per file.
    """
    results = []
    for file in files:
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            if file.filename.lower().endswith(".pdf"):
                result = extract_pdf_text_and_tables(temp_path)
            elif file.filename.lower().endswith(".docx"):
                result = load_docx(temp_path)
            else:
                results.append({"filename": file.filename, "error": "Unsupported file type"})
                continue
            text = result["text"]
            clauses = split_clauses(text)

            for table_index, table in enumerate(result.get("tables", []) or [], start=1):
                table_text = "\n".join(["\t".join(row) for row in table])
                clauses.append(
                    {
                        "clause_id": f"TABLE_{table_index}",
                        "section": f"Table {table_index}",
                        "level": "table",
                        "text": table_text,
                    }
                )
            stats = embed_and_store(clauses, file.filename)
            results.append({
                "filename": file.filename,
                "clauses_indexed": stats["clauses"],
                "status": "cached" if stats.get("cached") else "success"
            })
        finally:
            os.remove(temp_path)
    return results



    # ==============================
    # SEARCH ENDPOINT: Semantic search for legal clauses
    # ==============================


@app.post("/search/")
async def search_endpoint(body: SearchRequest = Body(...)):
    """
    Semantic search for legal clauses.
    Body: {"query": str, "k": int}
    Returns: {"results": [...]} 
    """
    results = search_clauses(body.query, body.k)
    return {"results": results}

