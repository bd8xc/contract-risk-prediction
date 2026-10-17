"""Small COI API. Run from Sem7: python -m uvicorn coi.api.main:app."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from pathlib import Path
from ..graph_manager import close_graph
from .routes import router

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


@asynccontextmanager
async def lifespan(app):
    yield
    close_graph()


app = FastAPI(title="COI risk analysis", version="2.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "coi", "database_check": "not_performed"}
