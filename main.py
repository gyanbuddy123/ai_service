import logging

from fastapi import FastAPI
from routers import generate, modify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="Gyaan Buddy AI Service",
    description="MCQ generation and modification via Claude Sonnet 4.6 (Vertex AI)",
    version="1.0.0",
)

app.include_router(generate.router)
app.include_router(modify.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
