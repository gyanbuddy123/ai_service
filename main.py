import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from routers import generate, modify, embed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("ai_service.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collection exists
    try:
        from services.vector_store import ensure_collection
        ensure_collection()
    except Exception as exc:
        logger.warning(f"Qdrant init failed (service may not be ready yet): {exc}")
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Gyaan Buddy AI Service",
    description="MCQ generation and modification via Claude Sonnet 4.6 (Vertex AI)",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(generate.router)
app.include_router(modify.router)
app.include_router(embed.router)


@app.get("/health")
async def health():
    qdrant_ok = False
    try:
        from services.vector_store import _get_qdrant, COLLECTION_NAME
        collections = {c.name for c in _get_qdrant().get_collections().collections}
        qdrant_ok = COLLECTION_NAME in collections
    except Exception:
        pass
    return {"status": "ok", "qdrant_collection_ready": qdrant_ok}
