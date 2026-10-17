from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from coordinator import router
from agent_api import router as agent_router
from coi.api.routes import router as coi_router
from agents.cl.confidentiality_leakage.router import router as indexed_cl_router
from ingestion_pipeline.ldi.app.main import router as ingestion_router

app = FastAPI(title="LexGuard", version="0.1.0")
app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)
app.include_router(router, prefix="/api")
app.include_router(coi_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api/ingestion")
app.include_router(indexed_cl_router, prefix="/api/ingestion", tags=["Indexed CL"])
WEB = ROOT / "web"
app.mount("/static", StaticFiles(directory=WEB), name="static")

PAGE_FILES = {
    "/": "index.html",
    "/review": "review.html",
    "/results": "results.html",
    "/workspaces": "workspaces.html",
    "/tools/conflicts": "conflicts.html",
    "/tools/clauses": "clauses.html",
    "/tools/confidentiality": "confidentiality.html",
    "/tools/litigation": "litigation.html",
    "/advanced": "advanced.html",
}


def page_response(filename: str):
    def serve_page() -> FileResponse:
        return FileResponse(WEB / filename)

    return serve_page


for path, filename in PAGE_FILES.items():
    app.add_api_route(path, page_response(filename), methods=["GET"], include_in_schema=False)
